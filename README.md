# The AI Stack

A reference map of public (and a few private) companies across the AI supply chain, plus a weekly automated stock-price pipeline and a manually-run SEC-filings updater. See `CLAUDE.md` for full project notes (layer model, data conventions, known limitations).

## What's here

- `index.html` — main reference page / site homepage. Hero with animated stat counters and a live "last refreshed" line, a sticky search + public/private filter + layer-pill toolbar, a scrolling ticker tape, and a sticky rail nav, followed by the 10-layer + Notable Stocks list. Below that, an embedded bubble/constellation view of the same roster (D3, click a layer to expand its companies). Company cards are rendered from a single in-page `LAYERS` data array — clicking one opens a modal combining its position in the stack (layer, upstream/downstream, public/private), its live price detail (60-day sparkline, 52-week range, YTD %, last-20-days %) read from `prices.json`, and its SEC filing info read from `sec_filings.json` (a link to the company's full EDGAR filings list, plus the date and a direct link to its most recent 10-K/20-F/40-F once that's been fetched). (Reworked from a plain list page by merging in a separate field-guide draft's UI — see "Notes on this cut" below. Originally renamed from `ai-stack-map.html` so GitHub Pages serves it at the site root.)
- `ai-stack-bubbles.html` — standalone full-screen companion bubble chart (name/ticker/role only — no price or SEC data wired in). Kept alongside the bubble view now embedded in `index.html` for anyone who wants to link directly to just the chart.
- `prices.json` — shared price data, machine-owned once the Action has run.
- `sec_filings.json` — shared SEC filing data (CIK, latest annual report date + link per ticker). Owned by whoever last ran `fetch_sec_filings.py` by hand and pushed the result — there's no Action for this one.
- `scripts/update_prices.py` — pulls weekly data from Yahoo Finance and rewrites `prices.json`. Runs automatically via GitHub Actions.
- `scripts/fetch_sec_filings.py` — pulls each ticker's latest annual report from SEC EDGAR and rewrites `sec_filings.json`. Imports its ticker list straight from `update_prices.py` rather than keeping a second copy. **Run manually** (`python scripts/fetch_sec_filings.py`, then `git add`/`commit`/`push` the result yourself) — intentionally not on a schedule; see "Notes on this cut" below for why.
- `.github/workflows/update-prices.yml` — runs the price script every Friday ~21:15 UTC (after US market close), and can be triggered manually from the Actions tab.
- `docs/` — deeper reference docs:
  - [`docs/data-flow.md`](docs/data-flow.md) — step-by-step trace of the weekly pipeline
  - [`docs/data-architecture.md`](docs/data-architecture.md) — `prices.json` schema, the click-to-detail UI, ticker classification, the 10-layer model, known limitations
  - [`docs/git-commands.md`](docs/git-commands.md) — git reference for pushing this repo and working with it day-to-day

## Publishing

1. Push this repo to GitHub.
2. Enable **GitHub Pages** (Settings → Pages → Source: **Deploy from a branch** → `main` → `/ (root)`). Do **not** pick the `/docs` folder option — that's this repo's markdown reference notes, not the site. `index.html` will be served at the site root automatically.

No API keys or secrets are needed — both the price pipeline and the SEC filings updater run entirely off free, keyless endpoints (Yahoo Finance and SEC EDGAR, respectively).

`ai-stack-bubbles.html` isn't linked from `index.html` (or vice versa) — share/link it directly, e.g. `https://<username>.github.io/<repo>/ai-stack-bubbles.html`, or add a nav link between the two if you want them connected.

## Notes on this cut

Assembled from the latest version of each file: an older, superseded duplicate of the market map page (pre back-button/live-metrics update) and a stale copy of the bubble map (missing the mobile back button) were dropped in favor of the newer content, and the market map was renamed `ai-stack-map.html` → `index.html` to serve as the GitHub Pages homepage.

A separate self-contained "field guide" draft (`index_2.html` in a later pass) — hero, animated stats, search/filter toolbar, layer-pill nav, ticker tape, and an embedded D3 bubble map, but with no price data wired in and a slightly stale company roster — was reworked into `index.html`: its UI chrome was merged onto the live page's data (91 companies, current tickers) and its price/sparkline modal, producing one page with both the list and bubble views plus live prices. The draft file itself was then retired.

The pipeline originally paired Yahoo Finance with an Alpaca fallback for tickers Yahoo missed. After two real weekly runs (0/81 and 0/80 tickers ever actually needed the fallback), Alpaca was removed entirely as unused complexity — `ALPACA_API_KEY`/`ALPACA_API_SECRET` are no longer read by the script or referenced in the workflow. If you added those secrets to the repo, they're safe to delete (Settings → Secrets and variables → Actions).

A second, independent script was added for SEC filing info: `scripts/fetch_sec_filings.py` looks up each ticker's CIK via SEC's bulk `company_tickers.json`, then reads its filing history from SEC EDGAR's `submissions` API to find the most recent 10-K (or 20-F/40-F for foreign private issuers like TSMC, ASML, Arm, SAP, Nebius), and writes `sec_filings.json`. Unlike the price pipeline, this one is **not** wired into a GitHub Action — it's run by hand (`python scripts/fetch_sec_filings.py`) and the resulting `sec_filings.json` is committed and pushed manually. Annual reports change rarely enough that a developer refreshing this occasionally is simpler than maintaining a second scheduled job on GitHub's servers. `sec_filings.json` starts as an empty seed file — the modal falls back to a generic "All filings ↗" EDGAR link (built straight from the ticker, no data file needed) until someone runs the script and pushes real data, at which point the "latest filing" line populates per company.
