# Data Flow: Weekly Price Pipeline

## End-to-end flow

```
GitHub Actions schedule (Fri 21:15 UTC)  ──or──  manual "Run workflow"
                │
                ▼
  .github/workflows/update-prices.yml
                │  checks out repo, sets up Python 3.12,
                │  pip install requests
                │  injects ALPACA_API_KEY / ALPACA_API_SECRET
                │  from repo Secrets into the environment
                ▼
      scripts/update_prices.py
                │
                ├─ 1. last_completed_close_date()
                │     works out the most recent finished US market session
                │
                ├─ 2. fetch_last_close(TICKERS, as_of_date)
                │     GET /v2/stocks/bars  → last daily close per ticker
                │
                ├─ 3. fetch_52w_ranges(TICKERS)
                │     GET /v2/stocks/bars  (~370 days, paginated)
                │     → running max(high) / min(low) per ticker
                │
                ├─ 4. fetch_ytd_start(TICKERS)
                │     GET /v2/stocks/bars  (first ~10 days of the year)
                │     → first trading-day close per ticker
                │
                └─ 5. writes prices.json (indent=2), stderr summary of
                      tickers written / tickers with no data returned
                ▼
   git-auto-commit-action (stefanzweifel/git-auto-commit-action@v5)
                │  commits prices.json if it changed
                │  message: "Weekly price update (Friday close)"
                ▼
        pushed straight to the default branch (main)
                │
                ▼
        index.html  (next page load)
                │  fetch('./prices.json', {cache: 'no-store'})
                ▼
        chip DOM updated with price / 52W / YTD, "Last refreshed" set
```

## Why the script resolves its own "as of" date

`last_completed_close_date()` does not trust "today" or a live snapshot. It:

1. Starts from the current UTC time.
2. Walks back to the last weekday if run on a weekend.
3. If run on a weekday *before* that day's ~21:05 UTC close, steps back one more session — so a Tuesday afternoon run still pulls Monday's close rather than Tuesday's still-forming bar.

This is why manual runs (Actions tab → **Run workflow**) are safe at any time — the script always resolves to the last *completed* session itself, and deliberately calls the `/bars` endpoint (historical daily bars) rather than `/snapshots` (which can return an in-progress bar during market hours). Don't swap this back to the snapshot endpoint.

Holiday handling is approximate — the date logic only knows Mon–Fri, not an actual market-holiday calendar. A run that lands on a holiday still resolves to that calendar date, but `fetch_last_close()` requests a 10-day lookback window and always takes the *last available bar* in it, so it naturally falls back to the prior real session regardless.

## Batching and pagination

All three fetch functions batch tickers in groups of 30 (Alpaca's multi-symbol query limit headroom) via `chunked()`. `fetch_52w_ranges` additionally paginates within each batch using `next_page_token`, since a year of daily bars for 30 symbols can exceed a single page.

## Failure behavior

- Each HTTP call uses `r.raise_for_status()` — a hard API error (bad auth, rate limit, outage) fails the whole run loudly, and no partial `prices.json` is written for that ticker set (the script only writes the file once, at the end, from data collected in memory).
- A ticker present in `TICKERS` but with no bars returned is recorded in `missing` and logged to stderr, but does not fail the run — the site simply keeps that ticker at "NA" until the next successful pull.
- `git-auto-commit-action` only commits when `prices.json` actually changed, so a no-op run doesn't create empty commits.

## Consumption on the page

`index.html` fetches `prices.json` once per page load (`cache: 'no-store'`, so it's never served stale from the browser cache), then computes and renders, per ticker: current price, %-from-52-week-high, %-from-52-week-low, and YTD % — all derived client-side from the raw numbers in the file. `ai-stack-bubbles.html` does not participate in this flow at all (see [data-architecture.md](./data-architecture.md)).

## Required secrets

| Secret | Where it's used | Notes |
|---|---|---|
| `ALPACA_API_KEY` | `scripts/update_prices.py` via env | Free/paper-trading key works — read-only market data, no trading |
| `ALPACA_API_SECRET` | same | Set both under repo **Settings → Secrets and variables → Actions** |

Without these two secrets set, the workflow will fail at the `Fetch prices from Alpaca` step (the script does `os.environ["ALPACA_API_KEY"]`, which raises `KeyError` if unset — there is no silent fallback).
