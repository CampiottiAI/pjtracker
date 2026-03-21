# Operations by domain

Stateless description of what the current app **does** (files [`src/app.py`](../../src/app.py), pages under [`src/`](../../src/)). Replace browser-specific behavior with equivalent API semantics.

---

## Notas Fiscais (NFs)

**Parse**

- Input: NF PDF bytes → `parse_nf_pdf()` — [`src/nf_parser.py`](../../src/nf_parser.py).
- If `usd` or `rate` is missing, treat as failed extraction (cannot compute BRL).
- Else `compute_brl(usd, rate, spread)`.

**Save**

- Require **`fiscal_mes`** (`YYYY-MM`).
- `save_pdf()` writes under `pdfs/` — [`src/app.py`](../../src/app.py).
- `save_nf_entry(...)` with all monetary + metadata fields; handle duplicate (no insert) and delete orphan PDF — pattern in [`src/NFs.py`](../../src/NFs.py).

**Images (optional, multiple)**

- After row exists, for each attachment: `save_image()` → `save_nf_image(nf_id, relative_path)` — [`src/app.py`](../../src/app.py). Paths stored relative to project root when possible.

**List / filter**

- `get_nf_entries(date_from, date_to)` or `get_nf_entries(fiscal_mes=...)`.

**Read one**

- `get_nf_by_id`, `get_nf_images`.

**Update**

- `update_nf_fiscal_mes(nf_id, fiscal_mes)`.

**Delete**

- `delete_nf(nf_id)` — removes row, PDF, all `nf_images` rows and image files.

**Serve PDF**

- Read bytes from `pdf_path` resolved against project root (current Streamlit uses `open_pdf_link` temp file — replace with HTTP response).

---

## Boletos

**Parse boleto PDF**

- `parse_boleto_pdf()` — [`src/boleto_parser.py`](../../src/boleto_parser.py).

**Parse receipt (optional)**

- `parse_receipt_image()` for value, datetime, barcode digits.

**Match status**

- Compare `codigo_barras_digits` from document vs receipt — see [`02-domain-rules-and-formats.md`](02-domain-rules-and-formats.md).

**Save**

- `save_boleto_pdf()` then `save_boleto_entry()`; on duplicate hash, delete new PDF.
- If receipt: `save_boleto_receipt()` then `update_boleto_receipt()` with `receipt_match_status` — [`src/app.py`](../../src/app.py). If receipt present, **receipt_date** must be set (validation in [`src/pages/4_Boletos.py`](../../src/pages/4_Boletos.py)).

**List**

- `get_boletos()` or `get_boletos(fiscal_mes=...)`.

**Update PDF**

- `update_boleto_pdf()` — replaces file, updates parsed fields; may fail if hash conflicts.

**Update receipt**

- Replace image file, `update_boleto_receipt()`; old file deleted before save in current flow.

**Update fiscal month**

- `update_boleto_fiscal_mes()`.

**Delete**

- `delete_boleto()` — row + PDF + receipt files.

---

## DARFs

Same operation set as boletos with DARF-specific parsers and persistence:

- Parse: `parse_darf_pdf()` — [`src/darf_parser.py`](../../src/darf_parser.py).
- Receipt: `parse_receipt_image()` (shared).
- Persistence: `save_darf_pdf`, `save_darf_entry`, `save_darf_receipt`, `update_darf_pdf`, `update_darf_receipt`, `update_darf_fiscal_mes`, `get_darfs`, `get_darf_by_id`, `delete_darf` — [`src/app.py`](../../src/app.py).
- Business rules mirrored in [`src/pages/5_DARFs.py`](../../src/pages/5_DARFs.py).

---

## Extratos

**Parse**

- Main: `parse_extrato_pdf()` (required for bundle).
- Optional: `parse_caixinha_pdf()`, `parse_higlobe_pdf()` — each can raise `RuntimeError` on LLM failure — [`src/extrato_parser.py`](../../src/extrato_parser.py).

**Save**

- Save PDF(s) with `save_extrato_pdf`, optionally `save_caixinha_pdf`, `save_higlobe_pdf`.
- `save_extrato_entry()` with JSON-serialized `entries` lists — [`src/app.py`](../../src/app.py).
- On duplicate `content_hash`, delete written PDFs for that attempt — [`src/pages/6_Extrato.py`](../../src/pages/6_Extrato.py).

**Product risk**

- Extraction is LLM-dependent; downstream consumers should treat fields as **review-needed**. The app surfaces a warning message after successful save/update in [`src/pages/6_Extrato.py`](../../src/pages/6_Extrato.py) — preserve as operational guidance, not UI text.

**Update**

- `update_extrato_pdf`, `update_caixinha_pdf`, `update_higlobe_pdf` — replace files and metadata.

**Remove attached PDFs only**

- `remove_caixinha_pdf(extrato_id)` — deletes file, nulls caixinha fields.
- `remove_higlobe_pdf(extrato_id)` — deletes file, nulls higlobe fields.

**List / get**

- `get_extratos`, `get_extrato_by_id`.

**Fiscal month**

- `update_extrato_fiscal_mes`.

**Delete**

- `delete_extrato` — removes row and extrato, caixinha, and higlobe PDF files.

---

## Analytics: NF charts (data only)

Source logic: [`src/pages/3_Gráficos.py`](../../src/pages/3_Gráficos.py).

**Input**

- Date range `[date_from, date_to]` inclusive on **parsed NF date** (calendar date from `nf_date` string).

**Rows included**

- From `get_nf_entries(date_from=..., date_to=...)`.
- Skip rows where `parse_nf_date_to_date(nf_date)` returns `None`.

**Per-point values**

| Field | Formula / source |
|-------|------------------|
| `usd` | `row["usd"]` or 0 |
| `brl_no_spread` | `row["brl_no_spread"]` or 0 |
| `brl_with_spread` | `row["brl_with_spread"]` or 0 |
| `rate` | `row["rate"]` or 0 |
| `spread` | `row["spread"]` or 0 |
| `effective_rate` | `rate * (1 - spread / 100)` |

**Sort**

- By date ascending.

**Series (three logical charts)**

1. `usd` vs date.
2. `brl_no_spread` and `brl_with_spread` vs date.
3. `rate` and `effective_rate` vs date — **numbers** follow the formulas above (legacy chart labels referred to these as with/without spread on the rate axis; see [`src/pages/3_Gráficos.py`](../../src/pages/3_Gráficos.py)).

---

## Fiscal month completeness

Source: [`src/pages/7_Mês_Fiscal.py`](../../src/pages/7_Mês_Fiscal.py).

**Discover months**

- Union of distinct non-empty `fiscal_mes` from `get_nf_entries()`, `get_boletos()`, `get_darfs()`, `get_extratos()`, sorted descending.

**Constants**

| Rule | Value |
|------|--------|
| `REQUIRED_NFS` | 2 |
| `REQUIRED_BOLETO_WITH_RECEIPT` | 1 |
| `REQUIRED_DARF_WITH_RECEIPT` | 1 |
| `REQUIRED_EXTRATO_COM_CAIXINHA` | 1 |

**Per month checks**

- NFs: count `get_nf_entries(fiscal_mes=fm)`.
- Boletos with receipt: `receipt_path` truthy.
- DARFs with receipt: same.
- Extratos with caixinha: `caixinha_pdf_path` truthy.
- Higlobe (optional): count extratos with `higlobe_pdf_path`; tracked separately — “optional” for closing; does not replace caixinha.

**Completeness**

- Month is complete when NF, boleto, DARF, and extrato (caixinha) rules all pass.
