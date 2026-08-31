# Data Flow: Price + SEC Filings Pipelines

Two independent pipelines feed the site: a weekly price pull (below) and a monthly SEC filings pull ([see that section](#data-flow-sec-filings-pipeline-monthly) further down). They run on separate schedules, write separate JSON files, and neither depends on the other.

## Weekly Price Pipeline

### End-to-end flow

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

### Data source: Yahoo Finance only

Yahoo Finance's public chart endpoint (`query1.finance.yahoo.com/v8/finance/chart/{symbol}`) is the **only** data source — free, needs no API key, and comfortably handles this project's ~80-ticker roster with one request per symbol (a small `time.sleep(0.2)` between requests keeps it polite).

An Alpaca Market Data API fallback existed for a while, tried per-symbol for whatever Yahoo didn't return. It was removed after two real weekly runs both showed 0 tickers ever actually needing it (0/81, 0/80 — either Yahoo covered everything, or the one failure was a dead ticker symbol that needed fixing at the source, not a retry via a second provider). `ALPACA_API_KEY`/`ALPACA_API_SECRET` are no longer read anywhere in this script or referenced in the workflow. If Yahoo ever does become unreliable enough to justify a second source, treat that as a fresh decision — don't just restore the old code from git history without re-evaluating it against whatever's actually failing at the time.

The trade-off of going Yahoo-only: its endpoint is unofficial and undocumented. It's been stable in practice, but it can change shape or start blocking without notice — with no fallback now, that would show up as the affected tickers dropping out of `prices.json` (logged under "No data returned for: ...") rather than the pipeline finding another way to get them.

### Why the script resolves its own "as of" date

`last_completed_close_date()` does not trust "today" or a live snapshot. It:

1. Starts from the current UTC time.
2. Walks back to the last weekday if run on a weekend.
3. If run on a weekday *before* that day's ~21:05 UTC close, steps back one more session — so a Tuesday afternoon run still pulls Monday's close rather than Tuesday's still-forming bar.

This is why manual runs (Actions tab → **Run workflow**) are safe at any time. `fetch_yahoo_bars` filters bars to `date <= as_of_date`, so an in-progress "today" bar returned during market hours is discarded, not treated as a completed close. Don't remove that filter — Yahoo's chart endpoint does return a partial current-day bar while the market is open.

Holiday handling is approximate — the date logic only knows Mon–Fri, not an actual market-holiday calendar. A run that lands on a holiday still resolves to that calendar date, but `fetch_yahoo_bars` always ends up using the *last available bar* at or before it, so it naturally falls back to the prior real session regardless.

### Failure behavior

- A single ticker failing on Yahoo (network error, bad response shape, no data) is logged and left out of `prices.json` for that run (under "No data returned for: ...") — it does not stop the run or affect any other ticker.
- `git-auto-commit-action` only commits when `prices.json` actually changed, so a no-op run doesn't create empty commits.

### Consumption on the page

`index.html` fetches `prices.json` once per page load (`cache: 'no-store'`) and keeps it in memory as `PRICES_DATA`. Nothing price-related is rendered until a company card is clicked — in the layer list, or a company bubble in the expanded constellation view — at which point the modal reads the ticker's entry directly out of `PRICES_DATA` and computes price, 52W/YTD/20-day percentages, and the sparkline/range-slider positions client-side, alongside the card's position in the stack (layer, upstream/downstream, public/private). `ai-stack-bubbles.html` does not participate in this flow at all (see [data-architecture.md](./data-architecture.md)).

<a id="data-flow-sec-filings-pipeline-monthly"></a>
## SEC Filings Pipeline (Monthly)

### End-to-end flow

```
GitHub Actions schedule (1st of month, 06:00 UTC)  ──or──  manual "Run workflow"
                │
                ▼
  .github/workflows/update-sec-filings.yml
                │  checks out repo, sets up Python 3.12,
                │  pip install requests
                ▼
      scripts/fetch_sec_filings.py
                │
                ├─ once: GET sec.gov/files/company_tickers.json
                │        → {ticker: (CIK, company name)} for the whole market
                │
                └─ for each ticker in TICKERS (imported from update_prices.py):
                      look up its CIK in that map
                      │
                      GET data.sec.gov/submissions/CIK##########.json
                      │  scan filings.recent.form for the first 10-K /
                      │  10-K405 / 20-F / 40-F (amendments skipped)
                      ▼
                      record {cik, companyName, formType, filingDate,
                      filingUrl} — filingUrl built from the CIK + that
                      filing's accession number
                ▼
   writes sec_filings.json (indent=2), stderr summary + any tickers with
   no CIK found or no annual filing found
                ▼
   git-auto-commit-action (stefanzweifel/git-auto-commit-action@v5)
                │  commits sec_filings.json if it changed
                │  message: "Monthly SEC filing info update"
                ▼
        pushed straight to the default branch (main)
                │
                ▼
        index.html  (next page load)
                │  fetch('./sec_filings.json', {cache: 'no-store'}) once,
                │  stored in SEC_DATA — no further network calls
                ▼
        card click → modal's SEC section reads SEC_DATA[ticker] for the
        "Latest filing" line; the "All filings ↗" link needs no fetched
        data at all — it's built straight from the ticker
```

### Data source: SEC EDGAR only

Two of SEC EDGAR's own free, keyless JSON endpoints cover this entirely — no API key, and (per SEC's guidance) a descriptive `User-Agent` header is enough to stay in good standing:

- `https://www.sec.gov/files/company_tickers.json` — a single bulk file mapping every ticker SEC tracks to its CIK (Central Index Key) and company name. Fetched once per run, not once per ticker.
- `https://data.sec.gov/submissions/CIK##########.json` — one company's full filing history. The script only reads the inline `filings.recent` arrays (parallel arrays: `form`, `filingDate`, `accessionNumber`, `primaryDocument`, all indexed together) and scans forward for the first annual-report-type entry.

Why monthly instead of weekly: 10-Ks are annual, 10-Qs quarterly — nothing in that cadence needs a weekly check. A monthly run comfortably catches a new annual filing within a few weeks of it posting.

Why 20-F/40-F alongside 10-K: several tickers in the roster are foreign private issuers that list via ADR/ADS on a US exchange (TSMC, ASML, Arm, SAP, Nebius) — they file `20-F` (or, for a Canadian filer, `40-F`) as their annual report instead of `10-K`. Scanning for any of `{10-K, 10-K405, 20-F, 40-F}` in one pass, rather than assuming `10-K`, means the script doesn't need a separate hardcoded list of "which tickers are foreign."

### Failure behavior

- A missing CIK (ticker not found in SEC's bulk map) is logged (`No SEC CIK found for: ...`) and that ticker is simply left out of `sec_filings.json` for the run — doesn't stop the rest.
- A CIK with no matching annual-report form in its recent filing window is logged separately (`No annual report found in range for: ...`) — expected to be rare to never in practice, given the window's size.
- `git-auto-commit-action` only commits when `sec_filings.json` actually changed, same as the price pipeline.

### Consumption on the page

`index.html` fetches `sec_filings.json` once per page load (`cache: 'no-store'`) into `SEC_DATA`, alongside (but independently of) the `prices.json` fetch. The modal's SEC section is shown for any company with `market:null` (the same eligibility as the price section) regardless of whether `SEC_DATA` has loaded yet or has an entry for that ticker — the "All filings ↗" link is constructed purely from `c.ticker`, so it always works; only the "Latest filing" line depends on `SEC_DATA[ticker]` existing, falling back to a "pending" message otherwise. `ai-stack-bubbles.html` does not participate in this flow at all, same as it doesn't for prices.

## Required secrets

None, for either pipeline. Prices run entirely off Yahoo Finance's free, keyless endpoint; SEC filings run entirely off SEC EDGAR's free, keyless JSON endpoints. No repo secrets are read anywhere in `scripts/update_prices.py`, `scripts/fetch_sec_filings.py`, or either workflow file.
