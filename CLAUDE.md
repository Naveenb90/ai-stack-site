# AI Stack — Project Notes

This repo holds a reference map of public (and a few private) companies across the AI supply chain, plus a weekly price-refresh pipeline and a monthly SEC-filings-refresh pipeline. Two viewer pages, two shared data files, two automated jobs.

## What's here

```
index.html                       # Main page — hero, search/filters, layer list, embedded bubble map
ai-stack-bubbles.html             # Standalone full-screen companion — same bubble map, no price/SEC data
prices.json                       # Shared price data, read by index.html at load time
sec_filings.json                  # Shared SEC filing data, read by index.html at load time
scripts/update_prices.py          # Pulls weekly data from Yahoo Finance, overwrites prices.json
scripts/fetch_sec_filings.py      # Pulls monthly filing data from SEC EDGAR, overwrites sec_filings.json
.github/workflows/update-prices.yml        # Runs update_prices.py every Friday after close
.github/workflows/update-sec-filings.yml   # Runs fetch_sec_filings.py monthly (1st, 06:00 UTC)
```

`ai-stack-bubbles.html` currently does **not** read `prices.json` or `sec_filings.json` — it's name/ticker/role only, no price or SEC data wired in. If that's wanted later, mirror the fetch logic from `index.html`'s `<script>` block.

## UI: index.html is one data-driven page, not static HTML chips

`index.html` was reworked from a plain static list into a single page built from an in-page `const LAYERS = [...]` array (each layer: id/num/name/tag/color/desc/companies, each company: name/ticker/role/market). Everything renders from that one array:

- **Hero** — animated stat counters (layers/companies/tracked tickers), a live "Last refreshed" line populated from `prices.json`'s `_meta.asOf`.
- **Sticky toolbar** — a search box (matches name + ticker), an All/Public/Private segmented filter, and layer-pill quick filters. Purely client-side, `applyFilters()` in the script.
- **Sticky rail nav** — jump links to each layer, active state via `IntersectionObserver` scrollspy.
- **Layer list** — same 10 layers + Notable Stocks as before, rendered as `.card` elements instead of the old static `.chip` divs.
- **Embedded bubble map** (`#bubbles`, D3 via CDN) — the constellation view, built from the *same* `LAYERS` array (`buildBubbles()`), so the list and bubble views on this page can't drift from each other — they share one data source.
- **Modal** — click (or Enter/Space on) a card, or a company bubble in the expanded constellation, and `openModal(c, layer)` opens one modal combining three things: a position line (`Layer X — Name · upstream/downstream · Public/Private`); for public US tickers, the full price detail — price, 60-day sparkline, 52W high/low with % from current, YTD %, last-20-days %, and a range slider, read straight out of `PRICES_DATA` (fetched once on page load); and, also for public US tickers, an SEC filings section — a generic "All filings ↗" link to the company's EDGAR filings list (built directly from the ticker, no data dependency) plus, once `SEC_DATA` has an entry for it, a "Latest 10-K/20-F/40-F — filed *date*" line linking straight to that filing. A `market:"private"`/`"non-us"` company, or a US ticker missing from `prices.json`, gets an explanatory empty state instead of the price block; the SEC section is hidden entirely for `market:"private"`/`"non-us"` companies (no US SEC filings to link to), and shows a "pending" message in place of the latest-filing line for any ticker not yet in `sec_filings.json`.

`ai-stack-bubbles.html` is unchanged — a separate standalone page with its own copy of the same roster in a JS array, kept for anyone who wants a link straight to just the bubble chart (linked from `index.html`'s hero and footer).

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

**When adding a new layer:** update the `LAYERS` array in `index.html` — its list view and embedded bubble view both read from it, so one edit covers both. Then separately update `ai-stack-bubbles.html`'s own array too — that page is still a fully independent copy of the same data, not a shared source. There's real drift risk between those two *files*; see "Known limitations" below.

## Data model: `prices.json`

```json
{
  "_meta": {
    "asOf": "2026-08-14",
    "source": "...",
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

- Only **US-listed tickers** appear here. Yahoo (the sole data source) doesn't cover foreign exchanges.
- `ytdStart` is the close on the year's first trading day — used to compute YTD % client-side.
- `history` is the last 60 daily closes, oldest first — powers the sparkline and the last-20-days stat (`history[length-21]` vs. current). Not a full audit trail, just enough for those two UI elements.
- The page computes everything else itself: % from 52-week high, % from 52-week low, YTD %, last-20-days %. `prices.json` never stores pre-computed percentages — only raw prices/closes. If you want to add a new derived metric, do the math in `index.html`'s modal-populate script, not in the Python script.
- A ticker with **no entry** in this file opens the modal in its empty state (see below) — the JS never blanks out or guesses.

## No-data states — this distinction matters

Two different reasons a chip's modal might not show stats:

- **Permanently no data** (`data-market="non-us"` or `data-market="private"` on the `.chip` div): Samsung, SK Hynix, Kioxia, Neo Performance Materials (all foreign-listed), and the five private AI labs (Anthropic, OpenAI, xAI, Mistral AI, Perplexity). The modal shows a fixed explanatory message and these are explicitly skipped by the pipeline — they will never be populated, because they're structurally out of scope (foreign exchange / no public ticker at all), not just missing data.
- **Pending** (any other US ticker not yet in `prices.json`): modal shows a "no data yet" message, but *will* populate automatically the next time `update_prices.py` runs successfully, as long as the ticker is in the `TICKERS` list in that script.

If you add a new company to the page, decide which bucket it's in and mark it accordingly — don't leave a fetchable US ticker without a `data-ticker` attribute, and don't add a foreign/private one without `data-market`.

## Data model: `sec_filings.json`

```json
{
  "TICKER": {
    "cik": "0000320193",
    "companyName": "Apple Inc.",
    "formType": "10-K",
    "filingDate": "2025-10-31",
    "filingUrl": "https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/0000320193-25-000079-index.htm"
  }
}
```

- Same eligibility as `prices.json`: only tickers with `market:null` are looked up. `market:"private"`/`"non-us"` companies are skipped — no SEC filings to find.
- `formType` is one of `10-K`, `10-K405`, `20-F`, or `40-F` — whichever annual-report type that filer actually uses (foreign private issuers like TSMC, ASML, Arm, SAP, and Nebius file `20-F`, not `10-K`). Amendments (`10-K/A`, `20-F/A`) are intentionally skipped in favor of the original filing.
- A ticker missing from this file isn't necessarily "no filings" — it just means `fetch_sec_filings.py` hasn't successfully resolved a CIK or annual filing for it yet (see stderr output from that script for `No SEC CIK found for: ...` / `No annual report found in range for: ...`).
- The modal never needs this file to show *something* — the generic "All filings ↗" EDGAR search link is built client-side straight from `c.ticker`, with no dependency on `sec_filings.json` having loaded or having an entry.

## The weekly pipeline

- `scripts/update_prices.py` runs every **Friday ~21:15 UTC** (~4:15pm ET, after US close) via the GitHub Action, and can also be triggered manually from the Actions tab.
- **Yahoo Finance is the sole data source.** Its public chart endpoint needs no API key and handles the ~80-ticker roster fine (one request per ticker, small delay between each). An Alpaca fallback existed briefly for whatever Yahoo didn't return, but was removed after two real weekly runs both showed 0 tickers ever needing it (0/81, 0/80) — pure unused complexity. `ALPACA_API_KEY`/`ALPACA_API_SECRET` are gone from both the script and the workflow's `env:` block; don't re-add them without a concrete reason (a Yahoo outage that actually happens, not a hypothetical one).
- **Manual triggers are safe at any time.** The script computes the *last completed* US market close itself (`last_completed_close_date()`) rather than trusting a live snapshot — so a Tuesday-afternoon manual run still pulls Monday's close, not a partial in-progress session. `fetch_yahoo_bars` filters bars to `date <= as_of_date`; Yahoo's chart endpoint returns a partial current-day bar during market hours, so don't remove that filter.
- Holiday handling is **approximate** — Mon–Fri only, no actual market-holiday calendar. A manual run on a holiday requests that date but naturally falls back to the last real session anyway (`fetch_yahoo_bars` always takes the last *available* bar, not a specific date match).
- `_meta.asOf` in the output reflects the *actual* session date the data came from, not just the requested date, so the page's "Last refreshed" line stays honest if the two ever disagree.

## The monthly SEC filings pipeline

- `scripts/fetch_sec_filings.py` runs on the **1st of every month at 06:00 UTC** via its own GitHub Action, and can also be triggered manually from the Actions tab. Annual reports don't need weekly checking the way prices do, hence the slower cadence.
- **SEC EDGAR is the sole data source**, via two of its free, keyless JSON endpoints: `https://www.sec.gov/files/company_tickers.json` (bulk ticker→CIK map, fetched once per run) and `https://data.sec.gov/submissions/CIK##########.json` per company (its filing history, scanned for the most recent `10-K`/`10-K405`/`20-F`/`40-F`). Both require a descriptive `User-Agent` header — see `SEC_HEADERS` in the script — SEC will reject requests without one.
- **Ticker list is imported, not duplicated.** `fetch_sec_filings.py` does `from update_prices import TICKERS` rather than keeping its own copy — these are two Python files in the same repo (not the two independent HTML rosters), so sharing the list here carries no real drift risk and one edit to `update_prices.py`'s `TICKERS` covers both pipelines.
- **Amendments are skipped on purpose.** If a company's most recent annual-report-type filing is a `10-K/A`, the script keeps looking for the original `10-K` instead — always link to the primary filing, not a correction, so this doesn't have to reason about what the amendment changed.
- A ticker can end up missing from `sec_filings.json` for two different reasons, both logged to stderr rather than failing the run: no CIK found in SEC's bulk ticker map (`No SEC CIK found for: ...`), or a CIK was found but no annual-report filing type showed up in its recent filing history (`No annual report found in range for: ...`, essentially never expected in practice — SEC's "recent" window covers far more than a year of filings for every company on this page).

## Adding a ticker

1. Add it to the `TICKERS` list in `scripts/update_prices.py` (US-listed only) — `fetch_sec_filings.py` picks it up automatically from the same list, no separate step needed there.
2. In `index.html`'s `LAYERS` array, add the company with `ticker:"SYMBOL"` and `market:null` (omit/null `market` for a pullable US ticker — only set it to `"private"` or `"non-us"` for companies neither pipeline can fetch). Add the same entry to `ai-stack-bubbles.html`'s own array too (see "known limitations" — no shared source between the two files).
3. It'll populate automatically on the next scheduled or manual run of each workflow — no other code changes needed.

## Known limitations / things not to "fix" without thinking first

- **No live prices.** Everything is a weekly snapshot. Don't add real-time polling without discussing rate limits and whether it's actually wanted — this was an explicit design choice (see conversation history / commit messages), not an oversight.
- **Two HTML files, no shared data source between them.** `index.html`'s list and its own embedded bubble view now share one `LAYERS` array *within that file*, but `ai-stack-bubbles.html` is still a fully separate file with its own independent copy of the roster. If you're changing the roster of companies, update both files or note that you didn't.
- **D3 loads from a CDN.** Both `index.html`'s embedded bubble map and `ai-stack-bubbles.html` load `d3.min.js` from `cdnjs.cloudflare.com` at runtime — fine for a public GitHub Pages site, but worth knowing if this ever needs to run somewhere with a stricter content-security policy.
- **Manual, human-verified seed data.** The current values in `prices.json` were originally researched and entered by hand before the automated pipeline existed. Once the Action has run at least once successfully, treat the file as machine-owned — don't hand-edit it and expect it to survive the next run.
- **Currency:** everything is USD except Neo Performance Materials (NEO), which is CAD and TSX-listed — it's in the permanent-no-data bucket precisely because of this, not a bug.
- **Yahoo's chart endpoint is unofficial/undocumented, and it's now the only data source.** It's been reliable in practice but can change shape or start blocking without notice. There is currently no fallback (Alpaca was removed as unused — see git log / README "Notes on this cut"). If Yahoo ever breaks outright, `missing` tickers just get logged and left out of `prices.json` for that run rather than failing the whole pipeline — check `docs/data-flow.md` before deciding whether a fallback is worth re-adding.
- **SEC EDGAR's bulk JSON endpoints are undocumented in the same sense Yahoo's chart endpoint is** — free and keyless, but not a formally versioned public API. `data.sec.gov`'s `submissions` response can be large for companies with a long filing history; the script only reads the inline `filings.recent` window (up to ~1000 most-recent filings), not the older paginated `filings.files` history — fine for finding the *latest* annual report, not a tool for a full filing archive.
- **`sec_filings.json` becomes machine-owned once its Action has run successfully at least once**, same as `prices.json` — don't hand-edit it afterward and expect it to survive the next run. Unlike `prices.json`, this file started as an empty seed (no hand-verified data) since the modal has a working fallback (the generic EDGAR link) with no data file at all.
- **This is a reference/illustrative tool, not investment advice.** Keep that framing in any copy changes — it's stated explicitly in the page footer and should stay there.
