#!/usr/bin/env python3
"""
Weekly pull: current price (last completed US market close), 52-week
high/low, the year's first trading-day close (for YTD %), and a ~60-session
daily-close history (for the sparkline / last-20-days stat), for every
US-listed ticker on the AI Stack page. Writes prices.json.

Data source: Yahoo Finance's public chart endpoint
(query1.finance.yahoo.com) — free, no API key required, one request per
ticker. This was previously paired with an Alpaca fallback for whatever
Yahoo didn't return; that fallback was removed after two real weekly runs
both showed 0 tickers ever actually needing it (0/81 and 0/80) — Yahoo
alone has been sufficient for this ~80-ticker roster. If Yahoo ever starts
failing on a meaningful number of tickers, look at re-adding a fallback
source rather than assuming it's a one-off.

NOTE: Yahoo only covers US-listed securities (NYSE, NASDAQ, etc). Tickers
on foreign exchanges (e.g. NEO on the TSX, Samsung/SK Hynix on the KRX,
Kioxia on the TSE) are NOT fetchable here and are intentionally excluded —
the page will keep showing their last static value. Private companies
(Anthropic, OpenAI, xAI, Mistral AI, Perplexity) have no ticker and are
excluded too.
"""

import json
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ai-stack-site price updater)"}
YAHOO_REQUEST_DELAY_SEC = 0.2  # be polite to the free, keyless endpoint

HISTORY_LEN = 60  # trading sessions kept for the sparkline / last-20-days stat

# US-listed tickers from the AI Stack page.
# Excluded on purpose: 005930.KS, 000660.KS, 285A.T (foreign exchanges),
# NEO (TSX), and Private (Anthropic/OpenAI/xAI/Mistral AI/Perplexity).
TICKERS = [
    "CDNS", "SNPS",
    "TSM", "ASML", "AMAT", "LRCX", "KLAC",
    "NVDA", "AVGO", "AMD", "INTC", "QCOM", "ARM", "CBRS",
    "LITE", "COHR", "AAOI", "VIAV", "MRVL", "CRDO", "ALAB", "ANET",
    "CSCO", "CIEN", "APH", "SMTC",
    "MU", "SNDK", "WDC", "STX", "P",
    "MSFT", "GOOGL", "META", "PLTR",
    "AMZN", "ORCL", "CRWV", "NBIS", "WYFI", "APLD", "IREN", "WULF", "CIFR", "HUT",
    "GLXY", "EQIX", "DLR",
    "CRWD", "PANW", "NET", "ZS", "FTNT", "DDOG",
    "VRT", "ETN", "GEV", "CEG", "VST", "PWR", "NVT", "NEE", "TLN", "OKLO", "BE",
    "AAPL", "DELL", "HPQ",
    "ADBE", "CRM", "SAP", "IBM", "CLS", "FLEX", "FN", "SANM",
    "AWK", "WTRG", "BMI", "LEU",
    "MP", "USAR",
]


def last_completed_close_date():
    """
    Best-effort date of the most recent completed US market close, whether
    this script runs on the Friday schedule or is triggered manually at any
    time/day. Approximate: treats Mon-Fri as trading days and 21:05 UTC as
    market close (4:05pm ET during EDT). Does NOT account for US market
    holidays — a manual run on a holiday still returns that calendar date,
    but fetch_yahoo_bars always takes the last *available* bar on/before
    it, so it naturally falls back to the prior real session either way.
    """
    now = datetime.now(timezone.utc)
    d = now.date()
    market_close_utc = now.replace(hour=21, minute=5, second=0, microsecond=0)

    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)

    if now < market_close_utc and now.date() == d:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)

    return d


def fetch_yahoo_bars(symbol, as_of_date):
    """
    Fetch ~1 year of daily bars for one symbol from Yahoo's public chart
    endpoint. Returns a list of {"t": "YYYY-MM-DD", "c": close, "h": high,
    "l": low} dicts, oldest first, filtered to sessions on/before
    as_of_date (so an in-progress "today" bar during market hours never
    gets treated as a completed close). Returns [] on any failure.
    """
    try:
        r = requests.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params={"range": "1y", "interval": "1d"},
            headers=YAHOO_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        result = r.json()["chart"]["result"][0]
        timestamps = result["timestamp"]
        quote = result["indicators"]["quote"][0]
        closes = quote["close"]
        highs = quote.get("high", closes)
        lows = quote.get("low", closes)
    except Exception as e:
        print(f"  Yahoo: {symbol} failed ({e})", file=sys.stderr)
        return []

    bars = []
    for ts, c, h, l in zip(timestamps, closes, highs, lows):
        if c is None:
            continue
        date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        if date > as_of_date:
            continue  # in-progress session — not a completed close yet
        bars.append({
            "t": date.isoformat(),
            "c": round(c, 4),
            "h": round(h, 4) if h is not None else round(c, 4),
            "l": round(l, 4) if l is not None else round(c, 4),
        })
    bars.sort(key=lambda b: b["t"])
    return bars


def fetch_all_bars(symbols, as_of_date):
    """Yahoo, per symbol. Returns {symbol: [bars...]} for whatever succeeded."""
    bars_by_symbol = {}
    for i, sym in enumerate(symbols):
        bars = fetch_yahoo_bars(sym, as_of_date)
        if bars:
            bars_by_symbol[sym] = bars
        if i < len(symbols) - 1:
            time.sleep(YAHOO_REQUEST_DELAY_SEC)
    return bars_by_symbol


def main():
    as_of_date = last_completed_close_date()
    print(f"Fetching {len(TICKERS)} tickers as of {as_of_date} (Yahoo Finance)...",
          file=sys.stderr)

    bars_by_symbol = fetch_all_bars(TICKERS, as_of_date)

    result = {}
    missing = []
    actual_dates = set()

    year_start = as_of_date.replace(month=1, day=1).isoformat()

    for sym in TICKERS:
        bars = bars_by_symbol.get(sym)
        if not bars:
            missing.append(sym)
            continue

        last = bars[-1]
        price = last["c"]
        actual_dates.add(last["t"])

        high52 = max(b["h"] for b in bars)
        low52 = min(b["l"] for b in bars)

        ytd_bar = next((b for b in bars if b["t"] >= year_start), None)
        ytd_start = ytd_bar["c"] if ytd_bar else None

        history = [round(b["c"], 2) for b in bars[-HISTORY_LEN:]]

        result[sym] = {
            "price": price,
            "high52": high52,
            "low52": low52,
            "ytdStart": ytd_start,
            "currency": "USD",
            "history": history,
        }

    reported_date = max(actual_dates) if actual_dates else as_of_date.isoformat()

    result["_meta"] = {
        "asOf": reported_date,
        "source": "Yahoo Finance — weekly pull, last completed US market close",
        "historyLength": HISTORY_LEN,
        "note": (
            "US market only. Foreign-listed tickers (TSX, KRX, TSE) and "
            "private companies are intentionally excluded — the page shows "
            "them as NA."
        ),
    }

    with open("prices.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote prices.json with {len(result) - 1} tickers, as of {reported_date}.",
          file=sys.stderr)
    if missing:
        print(f"No data returned for: {', '.join(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
