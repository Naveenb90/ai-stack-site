#!/usr/bin/env python3
"""
Periodic pull: each US-listed ticker's most recent annual report on file
with the SEC (10-K for domestic filers, 20-F/40-F for foreign private
issuers), plus a direct link to that filing. Writes sec_filings.json.

Data source: SEC EDGAR's public JSON APIs — no API key required.
  1. https://www.sec.gov/files/company_tickers.json   (ticker -> CIK)
  2. https://data.sec.gov/submissions/CIK##########.json  (filing history)

SEC asks every automated caller to identify itself with a descriptive
User-Agent (see https://www.sec.gov/os/webmaster-faq#developers) and to
stay under ~10 requests/second — SEC_HEADERS / SEC_REQUEST_DELAY_SEC below
cover both.

This mirrors update_prices.py's shape on purpose (same TICKERS list,
imported directly rather than duplicated — these are two Python files in
the same repo, not the two independent HTML rosters, so there's no drift
risk in sharing this one). Unlike the weekly price pull, annual reports
don't need weekly refreshing — this is meant to run monthly (see
.github/workflows/update-sec-filings.yml).
"""

import json
import sys
import time
from datetime import date, timezone

import requests

from update_prices import TICKERS

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SEC_HEADERS = {
    "User-Agent": "ai-stack-site SEC filing updater (github.com/Naveenb90/ai-stack-site)",
    "Accept-Encoding": "gzip, deflate",
}
SEC_REQUEST_DELAY_SEC = 0.15  # stay well under SEC's ~10 req/sec guidance

TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"

# Annual-report form types, most to check. Amendments (10-K/A, 20-F/A) are
# intentionally excluded — always link to the original filing, not a later
# correction, so this doesn't have to reason about what the amendment changed.
ANNUAL_FORMS = {"10-K", "10-K405", "20-F", "40-F"}


def fetch_ticker_to_cik():
    """
    SEC's own bulk ticker->CIK map. Keyed by an arbitrary integer; each
    value is {"cik_str": int, "ticker": "AAPL", "title": "Apple Inc."}.
    Returns {ticker: (cik10_str, title)}.
    """
    try:
        r = requests.get(TICKER_MAP_URL, headers=SEC_HEADERS, timeout=20)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        print(f"Failed to fetch {TICKER_MAP_URL}: {e}", file=sys.stderr)
        return {}

    mapping = {}
    for entry in raw.values():
        ticker = entry.get("ticker", "").upper()
        cik = entry.get("cik_str")
        title = entry.get("title", "")
        if ticker and cik is not None:
            mapping[ticker] = (str(cik).zfill(10), title)
    return mapping


def fetch_latest_annual_filing(cik10):
    """
    Look up one CIK's filing history and return the most recent annual
    report as {"formType", "filingDate", "accessionNumber", "primaryDocument"},
    or None if nothing in ANNUAL_FORMS shows up in the "recent" window
    (SEC returns up to ~1000 most-recent filings inline — enough for every
    company on this page to have at least one annual report in range).
    """
    try:
        r = requests.get(
            SUBMISSIONS_URL.format(cik10=cik10),
            headers=SEC_HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        recent = r.json()["filings"]["recent"]
        forms = recent["form"]
        dates = recent["filingDate"]
        accns = recent["accessionNumber"]
        docs = recent["primaryDocument"]
    except Exception as e:
        print(f"  submissions lookup failed for CIK{cik10}: {e}", file=sys.stderr)
        return None

    for i, form in enumerate(forms):
        if form in ANNUAL_FORMS:
            return {
                "formType": form,
                "filingDate": dates[i],
                "accessionNumber": accns[i],
                "primaryDocument": docs[i] if i < len(docs) else None,
            }
    return None


def build_filing_url(cik10, accession_number):
    cik_no_leading_zeros = str(int(cik10))
    accession_no_dashes = accession_number.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_no_leading_zeros}/"
        f"{accession_no_dashes}/{accession_number}-index.htm"
    )


def main():
    print(f"Looking up SEC CIKs for {len(TICKERS)} tickers...", file=sys.stderr)
    ticker_to_cik = fetch_ticker_to_cik()
    if not ticker_to_cik:
        print("Aborting: could not load SEC's ticker->CIK map.", file=sys.stderr)
        sys.exit(1)

    result = {}
    no_cik = []
    no_annual_filing = []

    for i, sym in enumerate(TICKERS):
        found = ticker_to_cik.get(sym)
        if not found:
            no_cik.append(sym)
        else:
            cik10, title = found
            filing = fetch_latest_annual_filing(cik10)
            if not filing:
                no_annual_filing.append(sym)
            else:
                result[sym] = {
                    "cik": cik10,
                    "companyName": title,
                    "formType": filing["formType"],
                    "filingDate": filing["filingDate"],
                    "filingUrl": build_filing_url(cik10, filing["accessionNumber"]),
                }
        if i < len(TICKERS) - 1:
            time.sleep(SEC_REQUEST_DELAY_SEC)

    result["_meta"] = {
        "asOf": date.today().isoformat(),
        "source": "SEC EDGAR — data.sec.gov submissions API",
        "note": (
            "Most recent 10-K (domestic filers) or 20-F/40-F (foreign "
            "private issuers) on file per ticker, as of this run. "
            "Amendments (…/A) are skipped in favor of the original filing. "
            "Runs monthly — annual reports don't need weekly refreshing."
        ),
    }

    with open("sec_filings.json", "w") as f:
        json.dump(result, f, indent=2)

    print(
        f"Wrote sec_filings.json with {len(result) - 1} tickers.",
        file=sys.stderr,
    )
    if no_cik:
        print(f"No SEC CIK found for: {', '.join(no_cik)}", file=sys.stderr)
    if no_annual_filing:
        print(f"No annual report found in range for: {', '.join(no_annual_filing)}", file=sys.stderr)


if __name__ == "__main__":
    main()
