# data/

This project was built on a **synthetic** financial dataset (fictional users, cards, and
card transactions — no real people or accounts). The full dataset is **not** included in this
repository for two reasons:

1. **Size** — `transactions.csv` is ~67 MB (~700,000 rows), too large for a clean Git repo.
2. **Privacy optics** — although the data is fake, the raw source files include columns such as
   `card_number`, `cvv`, home `address`, and geographic coordinates. Those are intentionally
   **removed** from everything published here.

## What's included (sanitized samples)

Small, sanitized samples are committed so you can see the schema and shape of the data:

| File | Rows | Notes |
|---|---|---|
| `users.sample.csv` | 15 | `address`, `latitude`, `longitude` columns removed |
| `cards.sample.csv` | 15 | `card_number`, `cvv` columns removed |
| `transactions.sample.csv` | 200 | no sensitive columns; trimmed to a small sample |
| `mcc_codes.json` | — | reference lookup: merchant-category codes → descriptions |
| `processed/mcc_category_map.json` | — | generated cache: MCC code → spending bucket (so categorization can run offline) |

## Running the app with the full dataset

The application expects the full files at `data/transactions.csv`, `data/cards.csv`, and
`data/users.csv` (git-ignored). To run it end-to-end, drop a compatible dataset in place using
the schemas shown by the sample files above. Without the full data, the samples still illustrate
the structure the code is built around.
