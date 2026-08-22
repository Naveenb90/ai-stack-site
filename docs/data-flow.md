# Data Flow: Weekly Price Pipeline

## End-to-end flow

```
GitHub Actions schedule (Fri 21:15 UTC)  ──or──  manual "Run workflow"
                │
                ▼
  .github/workflows/update-prices.yml
                │  checks out repo, sets up Python 3.12,
                │  pip install requests
                ▼
      scripts/update_prices.py
                │
                └─ for each ticker (one at a time):
                      fetch_yahoo_bars(symbol) — GET query1.finance.yahoo.com,
                      ~1y of daily bars, no API key, filtered to sessions
                      on/before the resolved "as of" date
                      │
                      per ticker that returned bars:
                      - price = last bar's close
                      - high52 / low52 = max/min over the fetched window
                      - ytdStart = first bar on/after Jan 1 of this year
                      - history = last 60 closes (oldest → newest)
                ▼
   writes prices.json (indent=2), stderr summary + list of any tickers
   with no data
                ▼
   git-auto-commit-action (stefanzweifel/git-auto-commit-action@v5)
                │  commits prices.json if it changed
                │  message: "Weekly price update (Friday close)"
                ▼
        pushed straight to the default branch (main)
                │
                ▼
        index.html  (next page load)
                │  fetch('./prices.json', {cache: 'no-store'}) once, stored
                │  in PRICES_DATA — no further network calls
                ▼
        card click (list view or expanded bubble) → modal reads
        PRICES_DATA[ticker], renders price, sparkline, 52W/YTD/20-day
        stats, range slider — alongside the card's position in the stack
```

## Data source: Yahoo Finance only

Yahoo Finance's public chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`) is the **only** data source — free, needs no API key, and comfortably handles this project's ~80-ticker roster with one request per symbol (a small `time.sleep(0.2)` between requests keeps it polite).

An Alpaca Market Data API fallback existed for a while, tried per-symbol for whatever Yahoo didn't return. It was removed after two real weekly runs both showed 0 tickers ever actually needing it (0/81, 0/80 — either Yahoo covered everything, or the one failure was a dead ticker symbol that needed fixing at the source, not a retry via a second provider). `ALPACA_API_KEY`/`ALPACA_API_SECRET` are no longer read anywhere in this script or referenced in the workflow. If Yahoo ever does become unreliable enough to justify a second source, treat that as a fresh decision — don't just restore the old code from git history without re-evaluating it against whatever's actually failing at the time.

The trade-off of going Yahoo-only: its endpoint is unofficial and undocumented. It's been stable in practice, but it can change shape or start blocking without notice — with no fallback now, that would show up as the affected tickers dropping out of `prices.json` (logged under "No data returned for: ...") rather than the pipeline finding another way to get them.

## Why the script resolves its own "as of" date

`last_completed_close_date()` does not trust "today" or a live snapshot. It:

1. Starts from the current UTC time.
2. Walks back to the last weekday if run on a weekend.
3. If run on a weekday *before* that day's ~21:05 UTC close, steps back one more session — so a Tuesday afternoon run still pulls Monday's close rather than Tuesday's still-forming bar.

This is why manual runs (Actions tab → **Run workflow**) are safe at any time. `fetch_yahoo_bars` filters bars to `date <= as_of_date`, so an in-progress "today" bar returned during market hours is discarded, not treated as a completed close. Don't remove that filter — Yahoo's chart endpoint does return a partial current-day bar while the market is open.

Holiday handling is approximate — the date logic only knows Mon–Fri, not an actual market-holiday calendar. A run that lands on a holiday still resolves to that calendar date, but `fetch_yahoo_bars` always ends up using the *last available bar* at or before it, so it naturally falls back to the prior real session regardless.

## Failure behavior

- A single ticker failing on Yahoo (network error, bad response shape, no data) is logged and left out of `prices.json` for that run (under "No data returned for: ...") — it does not stop the run or affect any other ticker.
- `git-auto-commit-action` only commits when `prices.json` actually changed, so a no-op run doesn't create empty commits.

## Consumption on the page

`index.html` fetches `prices.json` once per page load (`cache: 'no-store'`) and keeps it in memory as `PRICES_DATA`. Nothing price-related is rendered until a company card is clicked — in the layer list, or a company bubble in the expanded constellation view — at which point the modal reads the ticker's entry directly out of `PRICES_DATA` and computes price, 52W/YTD/20-day percentages, and the sparkline/range-slider positions client-side, alongside the card's position in the stack (layer, upstream/downstream, public/private). `ai-stack-bubbles.html` does not participate in this flow at all (see [data-architecture.md](./data-architecture.md)).

## Required secrets

None. The pipeline runs entirely off Yahoo Finance's free, keyless endpoint — no repo secrets are read anywhere in `scripts/update_prices.py` or referenced in `.github/workflows/update-prices.yml`.
