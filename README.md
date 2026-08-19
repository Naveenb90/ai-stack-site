# The AI Stack

A reference map of public (and a few private) companies across the AI supply chain, plus a weekly stock-price refresh pipeline. See `CLAUDE.md` for full project notes (layer model, data conventions, known limitations).

## What's here

- `index.html` — main reference page / site homepage (list view, 10 layers + Notable Stocks). Fetches `prices.json` at load time for live price/52-week/YTD stats. (Renamed from `ai-stack-map.html` so GitHub Pages serves it at the site root.)
- `ai-stack-bubbles.html` — companion interactive drill-down bubble chart (name/ticker/role only — no price data wired in).
- `prices.json` — shared price data, machine-owned once the Action has run.
- `scripts/update_prices.py` — pulls weekly data from Alpaca and rewrites `prices.json`.
- `.github/workflows/update-prices.yml` — runs the script every Friday ~21:15 UTC (after US market close), and can be triggered manually from the Actions tab.
- `docs/` — deeper reference docs:
  - [`docs/data-flow.md`](docs/data-flow.md) — step-by-step trace of the weekly Alpaca → `prices.json` → page pipeline
  - [`docs/data-architecture.md`](docs/data-architecture.md) — `prices.json` schema, ticker classification, the 10-layer model, known limitations
  - [`docs/git-commands.md`](docs/git-commands.md) — git reference for pushing this repo and working with it day-to-day

## Publishing

1. Push this repo to GitHub.
2. In **Settings → Secrets and variables → Actions**, add `ALPACA_API_KEY` and `ALPACA_API_SECRET` (free/paper-trading keys work) so the weekly price-update workflow can run.
3. Enable **GitHub Pages** (Settings → Pages → Source: **Deploy from a branch** → `main` → `/ (root)`). Do **not** pick the `/docs` folder option — that's this repo's markdown reference notes, not the site. `index.html` will be served at the site root automatically.

`ai-stack-bubbles.html` isn't linked from `index.html` (or vice versa) — share/link it directly, e.g. `https://<username>.github.io/<repo>/ai-stack-bubbles.html`, or add a nav link between the two if you want them connected.

## Notes on this cut

Assembled from the latest version of each file: an older, superseded duplicate of the market map page (pre back-button/live-metrics update) and a stale copy of the bubble map (missing the mobile back button) were dropped in favor of the newer content, and the market map was renamed `ai-stack-map.html` → `index.html` to serve as the GitHub Pages homepage. A separate self-contained "field guide" draft called `index.html` found alongside these files was left out entirely — `CLAUDE.md`'s own project notes describe this repo as just the two pages above, and don't mention it.
