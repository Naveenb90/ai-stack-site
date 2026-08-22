# Data Architecture

## Overview

The site is two static HTML pages sharing one JSON data file. There is no backend and no database — `prices.json` *is* the database, checked into git and rewritten in place by a scheduled job.

```
┌───────────────────────────┐        ┌──────────────────────┐
│        index.html          │──────▶│     prices.json        │
│  one LAYERS array drives:  │  GET  │  (static JSON, in repo)│
│  - layer list (cards)      │       └───────────▲────────────┘
│  - embedded bubble map     │                    │ overwrites
│  (fetches at load,         │        ┌──────────┴────────────┐
│   renders on click)        │        │ scripts/update_prices.py│
└───────────────────────────┘        │ (Yahoo Finance only)     │
┌─────────────────────┐              └──────────────────────┘
│ ai-stack-bubbles.html│
│ standalone full-screen│
│ bubble map, own copy  │
│ of the roster — no    │
│ price fetch            │
└─────────────────────┘
```

`ai-stack-bubbles.html` intentionally does **not** read `prices.json`. If price data is wanted there later, mirror the `fetch('./prices.json')` block from `index.html`'s `<script>` tag.

## UI: one data-driven page, click a company for detail

`index.html` renders from a single in-page `const LAYERS = [...]` array (each company: `name`/`ticker`/`role`/`market`) — both the layer list (`.card` elements) and the embedded bubble/constellation section read from it, so they can't drift from each other within this file. Cards show only the company name, role, and ticker symbol — no inline price or % badges. Clicking (or Enter/Space on a focused card, or clicking an expanded company bubble) opens a modal combining two things: the company's position in the stack (layer, upstream/downstream, public/private) and, for public US tickers, its price detail — current price, a 60-session sparkline, 52-week high/low with % from current, YTD %, last-20-days %, and a range slider positioning the price between the 52-week low and high. No network call happens at click time — everything needed is already in `prices.json`, fetched once on page load, which keeps the page fully static and avoids exposing any API credentials or hitting CORS issues client-side.

For a company with `market:"private"` or `market:"non-us"`, or a US ticker with no entry yet in `prices.json`, the modal shows an explanatory empty state instead of price stats (the position section still renders normally).

## `prices.json` schema

```json
{
  "_meta": {
    "asOf": "2026-08-14",
    "source": "Yahoo Finance — weekly pull, last completed US market close",
    "historyLength": 60,
    "note": "US market only. Foreign-listed tickers ... are intentionally excluded ..."
  },
  "TICKER": {
    "price": 123.45,
    "high52": 200.00,
    "low52": 100.00,
    "ytdStart": 110.00,
    "currency": "USD",
    "history": [118.20, 119.05, "...60 closes, oldest to newest, most recent = price"]
  }
}
```

Rules:

- Only raw prices (plus the `history` array) are stored. `index.html` computes %-from-52W-high, %-from-52W-low, YTD%, and last-20-days% client-side — never store a pre-computed percentage in this file.
- `history` holds the last `historyLength` (60) daily closes, oldest first, rounded to 2 decimals. It powers both the sparkline and the last-20-days stat (`history[history.length - 21]` vs. current price) — it is not a full audit trail, just enough for those two UI elements.
- `ytdStart` is the close on the year's first trading day, used for the YTD% calculation.
- `_meta.asOf` reflects the *actual* session date the data came from, which may occasionally differ from the requested date — this keeps the page's "Last refreshed" line honest.
- A ticker with no entry in this file falls back to its default empty-state rendering in the modal. The JS never blanks out or guesses a value.

## Company/ticker classification

Every company entry in `index.html`'s `LAYERS` array falls into exactly one of three states:

| State | How it's marked | Behavior |
|---|---|---|
| **Live** | `ticker:"SYM"`, `market:null` | Populated by `update_prices.py` on every successful run |
| **Pending** | `ticker:"SYM"`, `market:null`, but not yet in `prices.json` | Modal shows "no data yet" until the next run picks it up (must also be in the `TICKERS` list in the script) |
| **Permanently no data** | `market:"non-us"` or `market:"private"` | Modal shows a fixed explanatory message; explicitly skipped by the pipeline forever — foreign-listed (Samsung, SK Hynix, Kioxia, Neo Performance Materials) or private (Anthropic, OpenAI, xAI, Mistral AI, Perplexity) |

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

- **Weekly snapshot only, not live prices.** This is a deliberate design choice, not an oversight — don't add real-time polling without discussing rate limits first.
- **No shared data source between the two HTML *files*** for company/layer data — `index.html`'s list and its own embedded bubble view share one `LAYERS` array within that file, but `ai-stack-bubbles.html` is a fully separate file with its own independent copy. A roster change must be applied to both files (or explicitly noted as not applied to the other).
- **`prices.json` becomes machine-owned once the Action has run successfully at least once.** The current committed copy is hand-verified seed data — don't hand-edit it after that point and expect it to survive the next run.
- **Currency:** everything is USD except Neo Performance Materials (NEO, CAD/TSX) — which is in the permanent-no-data bucket specifically because it's foreign-listed, not because of the currency itself.
- **Holiday handling is approximate** (Mon–Fri only, no real market-holiday calendar) — see [data-flow.md](./data-flow.md) for how the script compensates.
- **Yahoo's chart endpoint is unofficial/undocumented, and it's the only data source (no fallback).** It's free and reliable in practice, but can change shape or start blocking without notice — see [data-flow.md](./data-flow.md) for what happens to affected tickers if it does.
- This is a reference/illustrative tool, not investment advice — keep that framing in any copy changes; it's stated in the page footer.
