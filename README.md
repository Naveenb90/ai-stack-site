# The AI Stack

A reference map of public (and a few private) companies across the AI supply chain, plus a weekly stock-price refresh pipeline. See `CLAUDE.md` for full project notes (layer model, data conventions, known limitations).

## What's here

- `index.html` — main reference page / site homepage. Hero with animated stat counters and a live "last refreshed" line, a sticky search + public/private filter + layer-pill toolbar, a scrolling ticker tape, and a sticky rail nav, followed by the 10-layer + Notable Stocks list. Below that, an embedded bubble/constellation view of the same roster (D3, click a layer to expand its companies). Company cards are rendered from a single in-page `LAYERS` data array — clicking one opens a modal combining its position in the stack (layer, upstream/downstream, public/private) with its live price detail (60-day sparkline, 52-week range, YTD %, last-20-days %) read from `prices.json`. (Reworked from a plain list page by merging in a separate field-guide draft's UI — see "Notes on this cut" below. Originally renamed from `ai-stack-map.html` so GitHub Pages serves it at the site root.)
- `ai-stack-bubbles.html` — standalone full-screen companion bubble chart (name/ticker/role only — no price data wired in). Kept alongside the bubble view now embedded in `index.html` for anyone who wants to link directly to just the chart.
- `prices.json` — shared price data, machine-owned once the Action has run.
- `scripts/update_prices.py` — pulls weekly data (Yahoo Finance primary, Alpaca fallback) and rewrites `prices.json`.
- `.github/workflows/update-prices.yml` — runs the script every Friday ~21:15 UTC (after US market close), and can be triggered manually from the Actions tab.
- `docs/` — deeper reference docs:
  - [`docs/data-flow.md`](docs/data-flow.md) — step-by-step trace of the weekly pipeline, and why Yahoo is primary / Alpaca is fallback
  - [`docs/data-architecture.md`](docs/data-architecture.md) — `prices.json` schema, the click-to-detail UI, ticker classification, the 10-layer model, known limitations
  - [`docs/git-commands.md`](docs/git-commands.md) — git reference for pushing this repo and working with it day-to-day

## Publishing

1. Push this repo to GitHub.
2. (Optional) In **Settings → Secrets and variables → Actions**, add `ALPACA_API_KEY` and `ALPACA_API_SECRET` (free/paper-trading keys work) if you want the Alpaca fallback active. The pipeline runs fine without them — it just relies entirely on Yahoo Finance.
3. Enable **GitHub Pages** (Settings → Pages → Source: **Deploy from a branch** → `main` → `/ (root)`). Do **not** pick the `/docs` folder option — that's this repo's markdown reference notes, not the site. `index.html` will be served at the site root automatically.

`ai-stack-bubbles.html` isn't linked from `index.html` (or vice versa) — share/link it directly, e.g. `https://<username>.github.io/<repo>/ai-stack-bubbles.html`, or add a nav link between the two if you want them connected.

## Notes on this cut

Assembled from the latest version of each file: an older, superseded duplicate of the market map page (pre back-button/live-metrics update) and a stale copy of the bubble map (missing the mobile back button) were dropped in favor of the newer content, and the market map was renamed `ai-stack-map.html` → `index.html` to serve as the GitHub Pages homepage.

A separate self-contained "field guide" draft (`index_2.html` in a later pass) — hero, animated stats, search/filter toolbar, layer-pill nav, ticker tape, and an embedded D3 bubble map, but with no price data wired in and a slightly stale company roster — was reworked into `index.html`: its UI chrome was merged onto the live page's data (91 companies, current tickers) and its price/sparkline modal, producing one page with both the list and bubble views plus live prices. The draft file itself was then retired.
