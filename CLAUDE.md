# AI Stack — Project Notes

This repo holds a reference map of public (and a few private) companies across the AI supply chain, plus a weekly price-refresh pipeline. Two viewer pages, one shared data file, one automated job.

## What's here

```
ai-stack-map.html                    # Main reference page — list view, 10 layers + Notable Stocks
ai-stack-bubbles.html                # Companion page — interactive drill-down bubble chart
prices.json                          # Shared price data, read by ai-stack-map.html at load time
scripts/update_prices.py             # Pulls weekly data from Alpaca, overwrites prices.json
.github/workflows/update-prices.yml  # Runs update_prices.py every Friday after close
```

`ai-stack-bubbles.html` currently does **not** read `prices.json` — it's name/ticker/role only, no price data wired in. If that's wanted later, mirror the fetch logic from `ai-stack-map.html`'s `<script>` block.

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

**When adding a new layer:** update it in both `ai-stack-map.html` (list) and `ai-stack-bubbles.html` (bubbles) — they're maintained as two independent copies of the same data, not a shared source. There's real drift risk here; see "Known limitations" below.

## Data model: `prices.json`

```json
{
  "_meta": {
    "asOf": "2026-08-14",
    "source": "...",
    "note": "..."
  },
  "TICKER": {
    "price": 123.45,
    "high52": 200.00,
    "low52": 100.00,
    "ytdStart": 110.00,
    "currency": "USD"
  }
}
```

- Only **US-listed tickers** appear here. Alpaca (the data source) doesn't cover foreign exchanges.
- `ytdStart` is the close on the year's first trading day — used to compute YTD % client-side.
- The page computes everything else itself: % from 52-week high, % from 52-week low, and YTD %. `prices.json` never stores pre-computed percentages — only raw prices. If you want to add a new derived metric, do the math in `ai-stack-map.html`'s populate script, not in the Python script.
- A ticker with **no entry** in this file renders as its default fallback in the HTML (see below) — the JS never blanks out or guesses.

## NA vs. pending — this distinction matters

Two different reasons a chip might not show a price, and the HTML treats them differently:

- **Permanently NA** (`data-market="non-us"` or `data-market="private"` on the `.chip` div): Samsung, SK Hynix, Kioxia, Neo Performance Materials (all foreign-listed), and the five private AI labs (Anthropic, OpenAI, xAI, Mistral AI, Perplexity). These are hardcoded to show "NA" with an explanatory tooltip and are explicitly skipped by the populate script — they will never be overwritten, because they're structurally out of scope for Alpaca (foreign exchange / no public ticker at all), not just missing data.
- **Pending** (any other US ticker not yet in `prices.json`): shows "NA" as a default too, but *will* populate automatically the next time `update_prices.py` runs successfully, as long as the ticker is in the `TICKERS` list in that script.

If you add a new company to the page, decide which bucket it's in and mark it accordingly — don't leave a fetchable US ticker without a `data-ticker` attribute, and don't add a foreign/private one without `data-market`.

## The weekly pipeline

- `scripts/update_prices.py` runs every **Friday ~21:15 UTC** (~4:15pm ET, after US close) via the GitHub Action, and can also be triggered manually from the Actions tab.
- **Manual triggers are safe at any time.** The script computes the *last completed* US market close itself (`last_completed_close_date()` + `fetch_last_close()`) rather than trusting a live snapshot — so a Tuesday-afternoon manual run still pulls Monday's close, not a partial in-progress session. This was a deliberate fix; don't revert to the snapshot endpoint (`/v2/stocks/snapshots`) for price data, it returns in-progress bars during market hours.
- Holiday handling is **approximate** — Mon–Fri only, no actual market-holiday calendar. A manual run on a holiday requests that date but naturally falls back to the last real session anyway (the script always takes the last *available* bar, not a specific date match).
- Requires two repo secrets: `ALPACA_API_KEY`, `ALPACA_API_SECRET`. Paper-trading keys work fine — this only reads market data, no trading.
- `_meta.asOf` in the output reflects the *actual* session date the data came from (from Alpaca's bar timestamps), not just the requested date, so the page's "Last refreshed" line stays honest if the two ever disagree.

## Adding a ticker to the weekly pull

1. Add it to the `TICKERS` list in `scripts/update_prices.py` (US-listed only).
2. In `ai-stack-map.html`, make sure its chip has `data-ticker="SYMBOL"` and no `data-market` attribute.
3. It'll populate automatically on the next scheduled or manual run — no other code changes needed.

## Known limitations / things not to "fix" without thinking first

- **No live prices.** Everything is a weekly snapshot. Don't add real-time polling without discussing rate limits and whether it's actually wanted — this was an explicit design choice (see conversation history / commit messages), not an oversight.
- **Two HTML files, no shared data source.** Layer/company data is duplicated between `ai-stack-map.html` and `ai-stack-bubbles.html`. If you're changing the roster of companies, update both or note that you didn't.
- **Manual, human-verified seed data.** The current values in `prices.json` were originally researched and entered by hand before the Alpaca pipeline existed. Once the Action has run at least once successfully, treat the file as machine-owned — don't hand-edit it and expect it to survive the next run.
- **Currency:** everything is USD except Neo Performance Materials (NEO), which is CAD and TSX-listed — it's in the permanent-NA bucket precisely because of this, not a bug.
- **This is a reference/illustrative tool, not investment advice.** Keep that framing in any copy changes — it's stated explicitly in the page footer and should stay there.
