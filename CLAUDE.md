# AI Stack — Project Notes

This repo holds a reference map of public (and a few private) companies across the AI supply chain, plus a weekly price-refresh pipeline. Two viewer pages, one shared data file, one automated job.

## What's here

```
index.html                    # Main page — hero, search/filters, layer list, embedded bubble map
ai-stack-bubbles.html                # Standalone full-screen companion — same bubble map, no price data
prices.json                          # Shared price data, read by index.html at load time
scripts/update_prices.py             # Pulls weekly data from Yahoo Finance, overwrites prices.json
.github/workflows/update-prices.yml  # Runs update_prices.py every Friday after close
```

`ai-stack-bubbles.html` currently does **not** read `prices.json` — it's name/ticker/role only, no price data wired in. If that's wanted later, mirror the fetch logic from `index.html`'s `<script>` block.

## UI: index.html is one data-driven page, not static HTML chips

`index.html` was reworked from a plain static list into a single page built from an in-page `const LAYERS = [...]` array (each layer: id/num/name/tag/color/desc/companies, each company: name/ticker/role/market). Everything renders from that one array:

- **Hero** — animated stat counters (layers/companies/tracked tickers), a live "Last refreshed" line populated from `prices.json`'s `_meta.asOf`.
- **Sticky toolbar** — a search box (matches name + ticker), an All/Public/Private segmented filter, and layer-pill quick filters. Purely client-side, `applyFilters()` in the script.
- **Sticky rail nav** — jump links to each layer, active state via `IntersectionObserver` scrollspy.
- **Layer list** — same 10 layers + Notable Stocks as before, rendered as `.card` elements instead of the old static `.chip` divs.
- **Embedded bubble map** (`#bubbles`, D3 via CDN) — the constellation view, built from the *same* `LAYERS` array (`buildBubbles()`), so the list and bubble views on this page can't drift from each other — they share one data source.
- **Modal** — click (or Enter/Space on) a card, or a company bubble in the expanded constellation, and `openModal(c, layer)` opens one modal combining both: a position line (`Layer X — Name · upstream/downstream · Public/Private`) *and*, for public US tickers, the full price detail — price, 60-day sparkline, 52W high/low with % from current, YTD %, last-20-days %, and a range slider, read straight out of `PRICES_DATA` (fetched once on page load). A `market:"private"`/`"non-us"` company, or a US ticker missing from `prices.json`, gets an explanatory empty state instead of the price block.

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

## The weekly pipeline

- `scripts/update_prices.py` runs every **Friday ~21:15 UTC** (~4:15pm ET, after US close) via the GitHub Action, and can also be triggered manually from the Actions tab.
- **Yahoo Finance is the sole data source.** Its public chart endpoint needs no API key and handles the ~80-ticker roster fine (one request per ticker, small delay between each). An Alpaca fallback existed briefly for whatever Yahoo didn't return, but was removed after two real weekly runs both showed 0 tickers ever needing it (0/81, 0/80) — pure unused complexity. `ALPACA_API_KEY`/`ALPACA_API_SECRET` are gone from both the script and the workflow's `env:` block; don't re-add them without a concrete reason (a Yahoo outage that actually happens, not a hypothetical one).
- **Manual triggers are safe at any time.** The script computes the *last completed* US market close itself (`last_completed_close_date()`) rather than trusting a live snapshot — so a Tuesday-afternoon manual run still pulls Monday's close, not a partial in-progress session. `fetch_yahoo_bars` filters bars to `date <= as_of_date`; Yahoo's chart endpoint returns a partial current-day bar during market hours, so don't remove that filter.
- Holiday handling is **approximate** — Mon–Fri only, no actual market-holiday calendar. A manual run on a holiday requests that date but naturally falls back to the last real session anyway (`fetch_yahoo_bars` always takes the last *available* bar, not a specific date match).
- `_meta.asOf` in the output reflects the *actual* session date the data came from, not just the requested date, so the page's "Last refreshed" line stays honest if the two ever disagree.

## Adding a ticker to the weekly pull

1. Add it to the `TICKERS` list in `scripts/update_prices.py` (US-listed only).
2. In `index.html`'s `LAYERS` array, add the company with `ticker:"SYMBOL"` and `market:null` (omit/null `market` for a pullable US ticker — only set it to `"private"` or `"non-us"` for companies the pipeline can't fetch). Add the same entry to `ai-stack-bubbles.html`'s own array too (see "known limitations" — no shared source between the two files).
3. It'll populate automatically on the next scheduled or manual run — no other code changes needed.

## Known limitations / things not to "fix" without thinking first

- **No live prices.** Everything is a weekly snapshot. Don't add real-time polling without discussing rate limits and whether it's actually wanted — this was an explicit design choice (see conversation history / commit messages), not an oversight.
- **Two HTML files, no shared data source between them.** `index.html`'s list and its own embedded bubble view now share one `LAYERS` array *within that file*, but `ai-stack-bubbles.html` is still a fully separate file with its own independent copy of the roster. If you're changing the roster of companies, update both files or note that you didn't.
- **D3 loads from a CDN.** Both `index.html`'s embedded bubble map and `ai-stack-bubbles.html` load `d3.min.js` from `cdnjs.cloudflare.com` at runtime — fine for a public GitHub Pages site, but worth knowing if this ever needs to run somewhere with a stricter content-security policy.
- **Manual, human-verified seed data.** The current values in `prices.json` were originally researched and entered by hand before the automated pipeline existed. Once the Action has run at least once successfully, treat the file as machine-owned — don't hand-edit it and expect it to survive the next run.
- **Currency:** everything is USD except Neo Performance Materials (NEO), which is CAD and TSX-listed — it's in the permanent-no-data bucket precisely because of this, not a bug.
- **Yahoo's chart endpoint is unofficial/undocumented, and it's now the only data source.** It's been reliable in practice but can change shape or start blocking without notice. There is currently no fallback (Alpaca was removed as unused — see git log / README "Notes on this cut"). If Yahoo ever breaks outright, `missing` tickers just get logged and left out of `prices.json` for that run rather than failing the whole pipeline — check `docs/data-flow.md` before deciding whether a fallback is worth re-adding.
- **This is a reference/illustrative tool, not investment advice.** Keep that framing in any copy changes — it's stated explicitly in the page footer and should stay there.
