#!/usr/bin/env python3
"""
Weekly pull: current price (last Friday close), 52-week high/low, and the
year's first trading-day close (for YTD %), for every US-listed ticker on
the AI Stack page. Writes prices.json; the page computes %-from-52W-high,
%-from-52W-low, and YTD % client-side from these raw numbers.

Requires env vars: ALPACA_API_KEY, ALPACA_API_SECRET
(Alpaca's free/paper-trading keys work fine for market data.)

NOTE: Alpaca only covers US-listed securities (NYSE, NASDAQ, etc).
Tickers on foreign exchanges (e.g. NEO on the TSX, Samsung/SK Hynix on the
KRX, Kioxia on the TSE) are NOT fetchable here and are intentionally
excluded — the page will keep showing their last static value.
Private companies (Anthropic, OpenAI, xAI, Mistral AI, Perplexity) have no
ticker and are excluded too.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

API_KEY = os.environ["ALPACA_API_KEY"]
API_SECRET = os.environ["ALPACA_API_SECRET"]
BASE_URL = "https://data.alpaca.markets/v2/stocks"
HEADERS = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET,
}

# US-listed tickers from the AI Stack page.
# Excluded on purpose: 005930.KS, 000660.KS, 285A.T (foreign exchanges),
# NEO (TSX), and Private (Anthropic/OpenAI/xAI/Mistral AI/Perplexity).
TICKERS = [
    "CDNS", "SNPS",
    "TSM", "ASML", "AMAT", "LRCX", "KLAC",
    "NVDA", "AVGO", "AMD", "INTC", "QCOM", "ARM", "CBRS",
    "LITE", "COHR", "AAOI", "VIAV", "MRVL", "CRDO", "ALAB", "ANET",
    "CSCO", "CIEN", "APH", "SMTC",
    "MU", "SNDK", "WDC", "STX", "PSTG",
    "MSFT", "GOOGL", "META", "PLTR",
    "AMZN", "ORCL", "CRWV", "NBIS", "APLD", "IREN", "WULF", "CIFR", "HUT",
    "GLXY", "EQIX", "DLR",
    "CRWD", "PANW", "NET", "ZS", "FTNT", "DDOG",
    "VRT", "ETN", "GEV", "CEG", "VST", "PWR", "NVT", "NEE", "TLN", "OKLO", "BE",
    "AAPL", "DELL", "HPQ",
    "ADBE", "CRM", "SAP", "IBM", "CLS", "FLEX", "FN", "SANM",
    "AWK", "WTRG", "BMI", "LEU",
    "MP", "USAR",
]


def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def last_completed_close_date():
    """
    Best-effort date of the most recent completed US market close, whether
    this script runs on the Friday schedule or is triggered manually at any
    time/day. Approximate: treats Mon-Fri as trading days and 21:05 UTC as
    market close (4:05pm ET during EDT). Does NOT account for US market
    holidays — a manual run on a holiday still returns that calendar date,
    but fetch_last_close() always takes the *last available bar* on/before
    it, so it naturally falls back to the prior real session either way.
    """
    now = datetime.now(timezone.utc)
    d = now.date()
    market_close_utc = now.replace(hour=21, minute=5, second=0, microsecond=0)

    # Weekend -> walk back to Friday.
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d -= timedelta(days=1)

    # Weekday, but before today's close -> use the previous completed
    # session, not today's still-forming bar.
    if now < market_close_utc and now.date() == d:
        d -= timedelta(days=1)
        while d.weekday() >= 5:
            d -= timedelta(days=1)

    return d


def fetch_last_close(symbols, as_of_date):
    """
    Close price from the most recent completed session on/before as_of_date.
    Uses the bars endpoint (not snapshots) so a manual mid-session trigger
    can't accidentally pick up an in-progress, not-yet-closed daily bar.
    """
    start = as_of_date - timedelta(days=10)  # buffer for holidays/weekends
    out = {}
    for batch in chunked(symbols, 30):
        r = requests.get(
            f"{BASE_URL}/bars",
            headers=HEADERS,
            params={
                "symbols": ",".join(batch),
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": as_of_date.isoformat(),
                "limit": 50,
                "adjustment": "split",
            },
            timeout=30,
        )
        r.raise_for_status()
        for sym, bars in r.json().get("bars", {}).items():
            if bars:
                out[sym] = {"price": bars[-1]["c"], "date": bars[-1]["t"][:10]}
    return out


def fetch_52w_ranges(symbols):
    """Max high / min low over the trailing ~365 days of daily bars."""
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=370)  # buffer for weekends/holidays
    out = {}
    for batch in chunked(symbols, 30):
        page_token = None
        while True:
            params = {
                "symbols": ",".join(batch),
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": 10000,
                "adjustment": "split",
            }
            if page_token:
                params["page_token"] = page_token
            r = requests.get(f"{BASE_URL}/bars", headers=HEADERS, params=params, timeout=30)
            r.raise_for_status()
            payload = r.json()
            for sym, bars in payload.get("bars", {}).items():
                if not bars:
                    continue
                highs = [b["h"] for b in bars]
                lows = [b["l"] for b in bars]
                if sym in out:
                    out[sym]["high52"] = max(out[sym]["high52"], max(highs))
                    out[sym]["low52"] = min(out[sym]["low52"], min(lows))
                else:
                    out[sym] = {"high52": max(highs), "low52": min(lows)}
            page_token = payload.get("next_page_token")
            if not page_token:
                break
    return out


def fetch_ytd_start(symbols):
    """First trading-day close of the current calendar year, per symbol."""
    today = datetime.now(timezone.utc).date()
    start = today.replace(month=1, day=1)
    # small buffer in case Jan 1-3 are holidays/weekend
    end = start + timedelta(days=10)
    out = {}
    for batch in chunked(symbols, 30):
        r = requests.get(
            f"{BASE_URL}/bars",
            headers=HEADERS,
            params={
                "symbols": ",".join(batch),
                "timeframe": "1Day",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "limit": 50,
                "adjustment": "split",
            },
            timeout=30,
        )
        r.raise_for_status()
        for sym, bars in r.json().get("bars", {}).items():
            if bars:
                out[sym] = bars[0]["c"]  # first bar of the year
    return out


def main():
    as_of_date = last_completed_close_date()
    print(f"Fetching {len(TICKERS)} tickers from Alpaca as of {as_of_date}...", file=sys.stderr)

    closes = fetch_last_close(TICKERS, as_of_date)
    ranges = fetch_52w_ranges(TICKERS)
    ytd_starts = fetch_ytd_start(TICKERS)

    result = {}
    missing = []
    actual_dates = set()
    for sym in TICKERS:
        close = closes.get(sym)
        if not close:
            missing.append(sym)
            continue
        actual_dates.add(close["date"])
        rng = ranges.get(sym, {})
        result[sym] = {
            "price": close["price"],
            "high52": rng.get("high52"),
            "low52": rng.get("low52"),
            "ytdStart": ytd_starts.get(sym),
            "currency": "USD",
        }

    # Report the actual session date the closes came from, not just the
    # requested as_of_date — they should usually match, but this keeps the
    # page's "Last refreshed" line honest if Alpaca's calendar disagrees.
    reported_date = max(actual_dates) if actual_dates else as_of_date.isoformat()

    result["_meta"] = {
        "asOf": reported_date,
        "source": "Alpaca Market Data API (weekly pull, last completed US market close)",
        "note": (
            "US market only. Foreign-listed tickers (TSX, KRX, TSE) and "
            "private companies are intentionally excluded — the page shows "
            "them as NA."
        ),
    }

    with open("prices.json", "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote prices.json with {len(result) - 1} tickers, as of {reported_date}.", file=sys.stderr)
    if missing:
        print(f"No data returned for: {', '.join(missing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
