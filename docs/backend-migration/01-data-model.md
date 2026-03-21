# Data model

All tables are created in `init_db()` in [`src/app.py`](../../src/app.py). Column names below match SQLite.

## `nf_entries`

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK | |
| `company` | TEXT | |
| `usd` | REAL NOT NULL | |
| `rate` | REAL NOT NULL | |
| `spread` | REAL NOT NULL | |
| `brl_no_spread` | REAL NOT NULL | |
| `brl_with_spread` | REAL NOT NULL | |
| `nf_date` | TEXT | e.g. `DD/MM/YYYY HH:MM:SS` |
| `verification_code` | TEXT | |
| `payment_via` | TEXT | e.g. Higlobe / Wise |
| `pdf_path` | TEXT | path to saved PDF |
| `fiscal_mes` | TEXT | `YYYY-MM` |
| `created_at` | TEXT ISO | |

**Uniqueness**: `INSERT OR IGNORE` plus unique index `idx_nf_entries_unique` on `(COALESCE(nf_date, ''), COALESCE(verification_code, ''), usd)` — see `save_nf_entry()` in [`src/app.py`](../../src/app.py).

## `nf_images`

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK | |
| `nf_id` | INTEGER NOT NULL | FK to `nf_entries.id` |
| `image_path` | TEXT NOT NULL | relative or absolute |
| `created_at` | TEXT ISO | |

## `boletos`

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK | |
| `pdf_path` | TEXT NOT NULL | |
| `receipt_path` | TEXT | optional |
| `value` | REAL | |
| `emission_date` | TEXT | e.g. `DD/MM/YYYY` |
| `deadline_date` | TEXT | |
| `receipt_date` | TEXT | e.g. `DD/MM/YYYY HH:MM:SS` |
| `codigo_barras` | TEXT | raw |
| `codigo_barras_digits` | TEXT | normalized digits |
| `receipt_value` | REAL | |
| `receipt_codigo_barras` | TEXT | |
| `receipt_codigo_barras_digits` | TEXT | |
| `receipt_match_status` | TEXT | `match` / `mismatch` / `NULL` |
| `content_hash` | TEXT | SHA-256 of value + dates — see `compute_boleto_content_hash()` |
| `fiscal_mes` | TEXT | `YYYY-MM` |
| `created_at` | TEXT ISO | |
| `updated_at` | TEXT ISO | |

**Uniqueness**: `idx_boletos_content_hash` unique on `content_hash` where not null.

## `darfs`

Same shape as `boletos` for PDF/receipt/barcode/hash/fiscal fields (`compute_darf_content_hash()`, `save_darf_entry()`, etc. in [`src/app.py`](../../src/app.py)). Unique index `idx_darfs_content_hash`.

## `extratos`

| Column | Type | Notes |
|--------|------|--------|
| `id` | INTEGER PK | |
| `extrato_pdf_path` | TEXT NOT NULL | main statement |
| `caixinha_pdf_path` | TEXT | optional |
| `higlobe_pdf_path` | TEXT | optional |
| `period_start` | TEXT | |
| `period_end` | TEXT | |
| `saldo_inicial` | REAL | |
| `rendimento` | REAL | |
| `total_entradas` | REAL | |
| `total_saidas` | REAL | |
| `saldo_final` | REAL | |
| `caixinha_saldo_final` | REAL | |
| `extrato_entries_json` | TEXT | JSON array of `dict` |
| `caixinha_entries_json` | TEXT | JSON array |
| `higlobe_entries_json` | TEXT | JSON array |
| `content_hash` | TEXT | from `period_start` \| `period_end` — `compute_extrato_content_hash()` |
| `fiscal_mes` | TEXT | `YYYY-MM` |
| `created_at` | TEXT ISO | |
| `updated_at` | TEXT ISO | |

**Uniqueness**: `idx_extratos_content_hash` unique on `content_hash` where not null.

## Path resolution

- Paths in the DB may be **relative to the project root** (parent of `pjtracker.db`).
- Helpers such as `delete_nf()`, `delete_boleto()`, `delete_darf()`, `delete_extrato()` resolve paths: if not absolute, join with `Path(DB_PATH).resolve().parent` — see [`src/app.py`](../../src/app.py).
- `save_pdf`, `save_boleto_pdf`, `save_darf_pdf`, `save_extrato_pdf`, etc. write under `pdfs/` and return `Path` objects; callers often store `str(path)` relative to the working directory.

## Streamlit-only artifact (not part of domain DB)

`STATIC_TEMP_DIR` in [`src/app.py`](../../src/app.py) (`src/static/temp/`) is used by `open_pdf_link()` for temporary PDFs for browser viewing. A FastAPI app should **serve downloads** or static files instead of this pattern.
