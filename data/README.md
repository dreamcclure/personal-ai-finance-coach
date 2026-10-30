# data/

This folder holds a small, **sanitized single-customer demo dataset** (customer **1696**) so the
app runs out of the box — including the live demo. The data is **synthetic** (fictional users,
cards, and transactions; no real people or accounts).

## What's included

| File | Contents |
|---|---|
| `transactions.csv` | Customer 1696's transactions only (~30k rows). No card numbers. |
| `users.csv` | Customer 1696's profile — `address`, `latitude`, `longitude` removed. |
| `cards.csv` | Customer 1696's card(s) — `card_number` and `cvv` removed. |
| `mcc_codes.json` | Reference lookup: merchant-category codes → descriptions. |
| `processed/mcc_category_map.json` | Cached MCC → spending bucket map, so categorization runs offline with no API call. |

## What's intentionally NOT included

- The **full multi-user dataset** (~700k transactions, ~67 MB). It's excluded for size and because
  the raw source files contain sensitive-looking columns (`card_number`, `cvv`, home `address`).
- Any real secrets — the LLM API key lives only in a local `.env` (see `.env.example`), never here.

## Running with more data

The app reads `data/transactions.csv`, `data/users.csv`, and `data/cards.csv`. To run it on a
larger dataset, replace these with files that follow the same column schema shown above.
