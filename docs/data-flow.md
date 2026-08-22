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
                │  from repo Secrets into the environment (optional —
                │  see "Two data sources" below)
                ▼
      scripts/update_prices.py
                │
                ├─ for each ticker (one at a time):
                │     1. fetch_yahoo_bars(symbol)  — GET query1.finance.yahoo.com,
                │        ~1y of daily bars, no API key, filtered to sessions
                │        on/before the resolved "as of" date
                │
                ├─ for whatever Yahoo didn't cover, batched by 30:
                │     2. fetch_alpaca_fallback(missing_symbols) — GET
                │        data.alpaca.markets/v2/stocks/bars (requires
                │        ALPACA_API_KEY/SECRET; skipped with a warning,
                │        not a crash, if they're unset)
                │
                └─ per ticker, derived from whichever source returned bars:
                      - price = last bar's close
                      - high52 / low52 = max/min over the fetched window
                      - ytdStart = first bar on/after Jan 1 of this year
                      - history = last 60 closes (oldest → newest)
                ▼
   writes prices.json (indent=2), stderr summary of sources used /
   tickers with no data from either source
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
        chip click → modal reads PRICES_DATA[ticker], renders price,
        sparkline, 52W/YTD/20-day stats, range slider
```

## Two data sources: Yahoo primary, Alpaca fallback

Yahoo Finance's public chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`) is the **primary** source — it's free, needs no API key, and comfortably handles this project's ~90-ticker roster with one request per symbol (a small `time.sleep(0.2)` between requests keeps it polite). Alpaca Market Data API is **fallback only**, tried per-symbol (batched by 30) for whatever Yahoo didn't return — an outage, a renamed/delisted symbol, or Yahoo's response shape changing unexpectedly.

This flip (Yahoo primary, Alpaca fallback — the opposite of the pipeline's original design) happened because Alpaca repeatedly failed in production: first a `401 Unauthorized` from a credentials issue, and this roster is large enough that Alpaca's free-tier limits were also a live concern. Yahoo has no such friction for this volume.

Alpaca credentials are read with `os.environ.get(...)`, not `os.environ[...]` — **they're optional now**. If `ALPACA_API_KEY`/`ALPACA_API_SECRET` aren't set, the fallback path is simply skipped (logged, not fatal); the run still succeeds off Yahoo alone as long as Yahoo covers the roster, which in practice it does. Don't revert this to a hard requirement — it would make the whole pipeline fail whenever Alpaca has any hiccup, even though Yahoo is doing all the real work.

The trade-off: Yahoo's endpoint is unofficial and undocumented. It's been stable in practice, but it can change shape or start blocking without notice, which is exactly the scenario the Alpaca fallback exists for. `_meta.sources` in `prices.json` records how many tickers came from each provider on the last run — check it occasionally.

## Why the script resolves its own "as of" date

`last_completed_close_date()` does not trust "today" or a live snapshot. It:

1. Starts from the current UTC time.
2. Walks back to the last weekday if run on a weekend.
3. If run on a weekday *before* that day's ~21:05 UTC close, steps back one more session — so a Tuesday afternoon run still pulls Monday's close rather than Tuesday's still-forming bar.

This is why manual runs (Actions tab → **Run workflow**) are safe at any time. Both fetch paths respect it: Yahoo's bars are filtered to `date <= as_of_date` (so an in-progress "today" bar returned during market hours is discarded, not treated as a completed close), and Alpaca's request window is bounded the same way. Don't remove that filter on the Yahoo side — its chart endpoint does return a partial current-day bar while the market is open.

Holiday handling is approximate — the date logic only knows Mon–Fri, not an actual market-holiday calendar. A run that lands on a holiday still resolves to that calendar date, but both fetch paths always end up using the *last available bar* at or before it, so they naturally fall back to the prior real session regardless.

## Failure behavior

- A single ticker failing on Yahoo (network error, bad response shape, no data) is logged and that ticker moves to the Alpaca-fallback list — it does not stop the run.
- If Alpaca credentials are missing or the Alpaca fallback call itself fails, those remaining tickers are just left missing for this run (logged under "No data returned for: ...") — the script still completes and writes whatever it did get.
- `git-auto-commit-action` only commits when `prices.json` actually changed, so a no-op run doesn't create empty commits.

## Consumption on the page

`index.html` fetches `prices.json` once per page load (`cache: 'no-store'`) and keeps it in memory as `PRICES_DATA`. Nothing is rendered until a chip is clicked — at that point the modal reads the ticker's entry directly out of `PRICES_DATA` and computes price, 52W/YTD/20-day percentages, and the sparkline/range-slider positions client-side. `ai-stack-bubbles.html` does not participate in this flow at all (see [data-architecture.md](./data-architecture.md)).

## Required secrets

| Secret | Where it's used | Notes |
|---|---|---|
| `ALPACA_API_KEY` | `scripts/update_prices.py` via env | **Optional.** Only needed if you want the Alpaca fallback to actually run; free/paper-trading key works |
| `ALPACA_API_SECRET` | same | Set both under repo **Settings → Secrets and variables → Actions** if you want the fallback active |

Without these two secrets set, the workflow still succeeds — it just relies entirely on Yahoo and logs a warning for any ticker Yahoo couldn't cover instead of trying Alpaca for it.
