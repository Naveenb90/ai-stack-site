# Data Architecture

## Overview

The site is two static HTML pages sharing one JSON data file. There is no backend and no database — `prices.json` *is* the database, checked into git and rewritten in place by a scheduled job.

```
┌─────────────────────┐        ┌──────────────────────┐
│  ai-stack-map.html   │──────▶│     prices.json        │
│  (fetches at load)   │  GET  │  (static JSON, in repo)│
└─────────────────────┘        └───────────▲────────────┘
                                            │ overwrites
┌─────────────────────┐        ┌──────────┴────────────┐
│ ai-stack-bubbles.html│        │ scripts/update_prices.py│
│ (no price fetch —     │        │ (Alpaca Market Data API)│
│  name/ticker/role only)│       └──────────────────────┘
└─────────────────────┘
```

`ai-stack-bubbles.html` intentionally does **not** read `prices.json`. If price data is wanted there later, mirror the `fetch('./prices.json')` block from `ai-stack-map.html`'s `<script>` tag.

## `prices.json` schema

```json
{
  "_meta": {
    "asOf": "2026-08-14",
    "source": "Alpaca Market Data API (weekly pull, last completed US market close)",
    "note": "US market only. Foreign-listed tickers ... are intentionally excluded ..."
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

Rules:

- Only raw prices are stored. `ai-stack-map.html` computes %-from-52W-high, %-from-52W-low, and YTD% client-side — never store a pre-computed percentage in this file.
- `ytdStart` is the close on the year's first trading day, used for the YTD% calculation.
- `_meta.asOf` reflects the *actual* session date the data came from (per Alpaca's bar timestamps), which may occasionally differ from the requested date — this keeps the page's "Last refreshed" line honest.
- A ticker with no entry in this file falls back to its default "NA" rendering in the HTML. The JS never blanks out or guesses a value.

## Company/ticker classification

Every ticker chip on `ai-stack-map.html` falls into exactly one of three states:

| State | How it's marked | Behavior |
|---|---|---|
| **Live** | `data-ticker="SYM"`, no `data-market` attribute | Populated by `update_prices.py` on every successful run |
| **Pending** | `data-ticker="SYM"`, ticker not yet in `prices.json` | Shows "NA" until the next run picks it up (must also be in the `TICKERS` list in the script) |
| **Permanently NA** | `data-market="non-us"` or `data-market="private"` | Hardcoded "NA" with a tooltip; explicitly skipped by the populate script forever — foreign-listed (Samsung, SK Hynix, Kioxia, Neo Performance Materials) or private (Anthropic, OpenAI, xAI, Mistral AI, Perplexity) |

Adding a new company means deciding which of the three buckets it belongs to and marking it accordingly.

## The 10-layer model

Both HTML pages share the same layer structure, ordered upstream → downstream, maintained as **two independent copies of the same data** (not a shared source — real drift risk if only one page is updated):

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
11. Notable Stocks — unnumbered catch-all for genuine "doesn't fit one layer" cases (diversified enterprise software, contract manufacturers, water utilities, rare-earth miners). Not a dumping ground; a new company should be placed in a real layer first.

## Known limitations

- **Weekly snapshot only, not live prices.** This is a deliberate design choice, not an oversight — don't add real-time polling without discussing Alpaca rate limits first.
- **No shared data source between the two HTML pages** for company/layer data — a roster change must be applied to both files (or explicitly noted as not applied to the other).
- **`prices.json` becomes machine-owned once the Action has run successfully at least once.** The current committed copy is hand-verified seed data — don't hand-edit it after that point and expect it to survive the next run.
- **Currency:** everything is USD except Neo Performance Materials (NEO, CAD/TSX) — which is in the permanent-NA bucket specifically because it's foreign-listed, not because of the currency itself.
- **Holiday handling is approximate** (Mon–Fri only, no real market-holiday calendar) — see [data-flow.md](./data-flow.md) for how the script compensates.
- This is a reference/illustrative tool, not investment advice — keep that framing in any copy changes; it's stated in the page footer.
