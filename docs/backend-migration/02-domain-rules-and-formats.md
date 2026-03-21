# Domain rules and formats

## Fiscal month (`fiscal_mes`)

- Stored as **`YYYY-MM`** (first day of month conceptually).
- Helpers in [`src/app.py`](../../src/app.py):
  - `format_fiscal_mes(value)` — display label e.g. `Março 2025` for valid input; `"—"` if empty.
  - `fiscal_mes_to_date(fiscal_mes)` — first day of month as `date`, or `None`.
  - `default_fiscal_mes_date()` — first day of **current** calendar month.

## NF dates

- **`nf_date` in DB**: typically full datetime string from extraction, e.g. `DD/MM/YYYY HH:MM:SS` (see `get_date_from_pdf` / LLM normalization in [`src/nf_parser.py`](../../src/nf_parser.py)).
- **Filtering by calendar range**: `get_nf_entries(date_from=..., date_to=...)` parses the **date part** only via `parse_nf_date_to_date()` (`%d/%m/%Y` from first token) — [`src/app.py`](../../src/app.py). Rows without a parseable date are **excluded** from filtered results.
- **Optional filter by fiscal month**: `get_nf_entries(fiscal_mes="YYYY-MM")` filters SQL `WHERE fiscal_mes = ?` (no date-range filter in that mode).

## Receipt datetime (boleto / DARF)

- Stored as **`DD/MM/YYYY HH:MM:SS`** in `receipt_date` when the client supplies date + optional time; time defaults to `00:00:00` if omitted in the current app logic — see save paths in [`src/pages/4_Boletos.py`](../../src/pages/4_Boletos.py) and [`src/pages/5_DARFs.py`](../../src/pages/5_DARFs.py).
- `parse_receipt_image()` may return `payment_datetime` in the same normalized format — [`src/boleto_parser.py`](../../src/boleto_parser.py).

## BRL computation for NFs

Spread semantics in `compute_brl()` — [`src/nf_parser.py`](../../src/nf_parser.py):

- `brl_no_spread = round(usd * rate, 2)`
- `effective_rate = rate * (1 - spread / 100)` (spread is a **percentage**; e.g. `3` means 3% reduction applied to the rate)
- `brl_with_spread = round(usd * effective_rate, 2)`

## Duplicate detection

### NF (natural key)

- `save_nf_entry()` uses `INSERT OR IGNORE` on `nf_entries` with unique index on `(nf_date, verification_code, usd)` with NULLs coalesced to `''` — [`src/app.py`](../../src/app.py).
- Returns `(inserted: bool, nf_id: int)`. If duplicate, `inserted` is false and `nf_id` is the existing row id.
- Current flow deletes the **newly saved PDF** if insert was skipped (orphan cleanup) — [`src/NFs.py`](../../src/NFs.py).

### Boleto / DARF (content hash)

- `compute_boleto_content_hash` / `compute_darf_content_hash`: SHA-256 of `"{value:.2f}|{emission_date}|{deadline_date}"` with empty string for missing; returns `None` if payload is effectively `"0||"` — [`src/app.py`](../../src/app.py).
- `save_boleto_entry` / `save_darf_entry` catch `sqlite3.IntegrityError` on duplicate `content_hash` — [`src/app.py`](../../src/app.py).
- Failed insert after writing PDF: callers delete the new PDF file on disk — e.g. [`src/pages/4_Boletos.py`](../../src/pages/4_Boletos.py).

### Extrato (period hash)

- `compute_extrato_content_hash(period_start, period_end)`: SHA-256 of `"{period_start}|{period_end}"`; `None` if both empty — [`src/app.py`](../../src/app.py).
- `save_extrato_entry` catches `IntegrityError`; callers remove extrato, caixinha, and higlobe PDFs written for that attempt — [`src/pages/6_Extrato.py`](../../src/pages/6_Extrato.py).

### PDF update conflicts (boleto / DARF)

- `update_boleto_pdf` / `update_darf_pdf` can return `False` on `IntegrityError` if another row already has the new content hash — [`src/app.py`](../../src/app.py).

## Barcode match status

- Compared on **digit strings** only: `document_digits == receipt_digits` → `"match"`, else `"mismatch"`; if either is missing → `None` — logic mirrored in [`src/pages/4_Boletos.py`](../../src/pages/4_Boletos.py) and [`src/pages/5_DARFs.py`](../../src/pages/5_DARFs.py).
- Human-readable diff for mismatches: `format_barcode_diff()` in [`src/barcode_diff.py`](../../src/barcode_diff.py) (unified diff style string).

## Edge case: verification code when saving NF

- UI may display `"-"` when verification code is missing; **save** still uses `verification_code` from parsed data (or `"-"` as string). `save_pdf()` sanitizes filename components — [`src/NFs.py`](../../src/NFs.py), [`src/app.py`](../../src/app.py) `save_pdf()`.
