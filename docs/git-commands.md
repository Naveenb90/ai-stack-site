# Git Commands Reference

This repo is already initialized locally with one commit on `main`. These are the commands to get it onto GitHub and to work with it day-to-day.

## First push to GitHub

1. Create an empty repo on GitHub (no README/license/gitignore — this repo already has its own), then:

```bash
cd ai-stack-site
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

Using SSH instead of HTTPS:

```bash
git remote add origin git@github.com:<your-username>/<your-repo>.git
git push -u origin main
```

2. Add the two required secrets so the price-update workflow can run: repo → **Settings → Secrets and variables → Actions → New repository secret** → add `ALPACA_API_KEY` and `ALPACA_API_SECRET`.

3. Optional: repo → **Settings → Actions → General → Workflow permissions** — confirm "Read and write permissions" is enabled, so `git-auto-commit-action` can push the weekly `prices.json` update back to `main`. (The workflow already declares `permissions: contents: write`, but this repo-level setting must also allow it.)

## Everyday workflow

```bash
git status                 # what changed
git add <file>              # stage specific file(s)
git add -A                  # stage everything (new, modified, deleted)
git commit -m "message"     # commit staged changes
git push                    # push to the tracked remote branch
git pull                    # fetch + merge (do this before starting new work,
                             # especially since the weekly Action pushes to main)
```

## Branching for a change

```bash
git checkout -b feature/add-new-layer
# ... edit files ...
git add -A
git commit -m "Add <layer/company> to both HTML pages"
git push -u origin feature/add-new-layer
# open a Pull Request on GitHub, merge into main when ready
git checkout main
git pull
git branch -d feature/add-new-layer   # clean up local branch after merge
```

## Checking the automated price-update history

Because the Action commits directly to `main`, weekly price refreshes show up as ordinary commits:

```bash
git log --oneline -- prices.json      # history of price-data commits
git log --oneline --author="github-actions"   # commits made by the bot
git show <commit-hash> -- prices.json # diff of a specific price update
```

Or from the GitHub UI: repo → **Actions** tab → **Update stock prices (weekly)** workflow → individual run logs. A manual run is available there too via **Run workflow**.

## Undoing things

```bash
git restore <file>              # discard uncommitted changes to a file
git restore --staged <file>     # unstage a file (keep the edits)
git revert <commit-hash>        # undo a pushed commit safely (new commit)
git reset --soft HEAD~1         # undo the last local commit, keep changes staged
```

Avoid `git push --force` on `main` — the weekly Action pushes there too, and a force-push can silently drop a price update that landed after your last pull.

## Useful checks before pushing

```bash
git diff                 # review unstaged changes
git diff --staged        # review staged changes
git log --oneline -5     # sanity-check recent history
```
