# AI Stack — Project Notes

This repo holds a reference map of public (and a few private) companies across the AI supply chain, plus a weekly price-refresh pipeline. Two viewer pages, one shared data file, one automated job.

## What's here

```
index.html                    # Main reference page — list view, 10 layers + Notable Stocks
ai-stack-bubbles.html                # Companion page — interactive drill-down bubble chart
prices.json                          # Shared price data, read by index.html at load time
scripts/update_prices.py             # Pulls weekly data (Yahoo primary, Alpaca fallback), overwrites prices.json
.github/workflows/update-prices.yml  # Runs update_prices.py every Friday after close
```

`ai-stack-bubbles.html` currently does **not** read `prices.json` — it's name/ticker/role only, no price data wired in. If that's wanted later, mirror the fetch logic from `index.html`'s `<script>` block.

## UI: click a ticker for detail, nothing shown inline

`index.html` chips show only name/role/ticker — no inline price or % badges. `PRICES_DATA` is fetched once on page load and kept in memory; clicking (or Enter/Space on) a chip opens a modal that reads that ticker's entry straight out of `PRICES_DATA` and renders price, a 60-day sparkline, 52W high/low with % from current, YTD %, last-20-days %, and a range slider — all computed client-side, no network call at click time. A `data-market="private"`/`"non-us"` chip, or a US ticker missing from `prices.json`, opens the modal with an explanatory empty state instead.

## The layer model

Both pages share the same 10-layer structure, ordered upstream → downstream, plus a catch-all:

1. Design Software (EDA)
2. Foundry & Equipment
3. Silicon
4. Networking & Optics
5. Memory
6. Models & Software
7. Cloud Infrastructure
8. Security
9. Power & Cooling
10. Consumer & Devices
11. Notable Stocks (unnumbered catch-all — companies that don't cleanly fit one layer: diversified enterprise software, contract manufacturers, water utilities, rare earth miners)

If you add a company, decide which layer it actually belongs to before defaulting to Notable Stocks — that section is for genuine "doesn't fit" cases, not a dumping ground.

**When adding a new layer:** update it in both `index.html` (list) and `ai-stack-bubbles.html` (bubbles) — they're maintained as two independent copies of the same data, not a shared source. There's real drift risk here; see "Known limitations" below.

## Data model: `prices.json`

```json
{
  "_meta": {
    "asOf": "2026-08-14",
    "source": "...",
    "sources": { "yahoo": 78, "alpaca": 3 },
    "historyLength": 60,
    "note": "..."
  },
  "TICKER": {
    "price": 123.45,
    "high52": 200.00,
    "low52": 100.00,
    "ytdStart": 110.00,
    "currency": "USD",
    "history": [118.20, "...60 closes, oldest to newest"]
  }
}
```

- Only **US-listed tickers** appear here. Neither Yahoo nor Alpaca (the two data sources) covers foreign exchanges.
- `ytdStart` is the close on the year's first trading day — used to compute YTD % client-side.
- `history` is the last 60 daily closes, oldest first — powers the sparkline and the last-20-days stat (`history[length-21]` vs. current). Not a full audit trail, just enough for those two UI elements.
- The page computes everything else itself: % from 52-week high, % from 52-week low, YTD %, last-20-days %. `prices.json` never stores pre-computed percentages — only raw prices/closes. If you want to add a new derived metric, do the math in `index.html`'s modal-populate script, not in the Python script.
- A ticker with **no entry** in this file opens the modal in its empty state (see below) — the JS never blanks out or guesses.

## No-data states — this distinction matters

Two different reasons a chip's modal might not show stats:

- **Permanently no data** (`data-market="non-us"` or `data-market="private"` on the `.chip` div): Samsung, SK Hynix, Kioxia, Neo Performance Materials (all foreign-listed), and the five private AI labs (Anthropic, OpenAI, xAI, Mistral AI, Perplexity). The modal shows a fixed explanatory message and these are explicitly skipped by the pipeline — they will never be populated, because they're structurally out of scope (foreign exchange / no public ticker at all), not just missing data.
- **Pending** (any other US ticker not yet in `prices.json`): modal shows a "no data yet" message, but *will* populate automatically the next time `update_prices.py` runs successfully, as long as the ticker is in the `TICKERS` list in that script.

If you add a new company to the page, decide which bucket it's in and mark it accordingly — don't leave a fetchable US ticker without a `data-ticker` attribute, and don't add a foreign/private one without `data-market`.

## The weekly pipeline

- `scripts/update_prices.py` runs every **Friday ~21:15 UTC** (~4:15pm ET, after US close) via the GitHub Action, and can also be triggered manually from the Actions tab.
- **Yahoo Finance is the primary source, Alpaca is fallback-only.** Yahoo's public chart endpoint needs no API key and handles the ~90-ticker roster fine (one request per ticker, small delay between each). Alpaca is tried, batched, only for whatever Yahoo didn't return — an outage, a bad symbol, Yahoo's response shape changing. This is a deliberate flip from the pipeline's original Alpaca-only design; don't revert it without a good reason (Alpaca repeatedly failed in production here, both on auth and on this roster's size vs. its free-tier limits).
- **Alpaca credentials are optional.** Read via `os.environ.get(...)`, not `os.environ[...]`. Missing secrets just skip the fallback (logged) rather than failing the whole run — Yahoo alone is expected to succeed.
- **Manual triggers are safe at any time.** The script computes the *last completed* US market close itself (`last_completed_close_date()`) rather than trusting a live snapshot — so a Tuesday-afternoon manual run still pulls Monday's close, not a partial in-progress session. Both fetch paths filter bars to `date <= as_of_date`; Yahoo's chart endpoint in particular returns a partial current-day bar during market hours, so don't remove that filter.
- Holiday handling is **approximate** — Mon–Fri only, no actual market-holiday calendar. A manual run on a holiday requests that date but naturally falls back to the last real session anyway (both fetch paths always take the last *available* bar, not a specific date match).
- `_meta.asOf` in the output reflects the *actual* session date the data came from, not just the requested date, so the page's "Last refreshed" line stays honest if the two ever disagree. `_meta.sources` records the yahoo/alpaca split for the run — worth checking occasionally for an unexpectedly high Alpaca count (a sign Yahoo is having a bad day).

## Adding a ticker to the weekly pull

1. Add it to the `TICKERS` list in `scripts/update_prices.py` (US-listed only).
2. In `index.html`, make sure its chip has `data-ticker="SYMBOL"` and no `data-market` attribute.
3. It'll populate automatically on the next scheduled or manual run — no other code changes needed.

## Known limitations / things not to "fix" without thinking first

- **No live prices.** Everything is a weekly snapshot. Don't add real-time polling without discussing rate limits and whether it's actually wanted — this was an explicit design choice (see conversation history / commit messages), not an oversight.
- **Two HTML files, no shared data source.** Layer/company data is duplicated between `index.html` and `ai-stack-bubbles.html`. If you're changing the roster of companies, update both or note that you didn't.
- **Manual, human-verified seed data.** The current values in `prices.json` were originally researched and entered by hand before the automated pipeline existed. Once the Action has run at least once successfully, treat the file as machine-owned — don't hand-edit it and expect it to survive the next run.
- **Currency:** everything is USD except Neo Performance Materials (NEO), which is CAD and TSX-listed — it's in the permanent-no-data bucket precisely because of this, not a bug.
- **Yahoo's chart endpoint is unofficial/undocumented.** It's been reliable in practice but can change shape or start blocking without notice — that's exactly why the Alpaca fallback exists. If Yahoo ever breaks outright, the Alpaca path (with valid secrets) is the stopgap, not a full replacement at current free-tier limits for this roster size.
- **This is a reference/illustrative tool, not investment advice.** Keep that framing in any copy changes — it's stated explicitly in the page footer and should stay there.
