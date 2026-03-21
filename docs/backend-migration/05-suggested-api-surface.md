# Suggested API surface (non-binding)

Sketch for a FastAPI backend. Paths are illustrative; use your own versioning (`/api/v1/...`) and auth.

## Principles

- **Multipart** for PDFs and images; return **JSON** for metadata and parsed previews.
- **Binary downloads** for stored PDFs/images (`Content-Type: application/pdf` or image MIME) instead of [`open_pdf_link()`](../../src/pjtracker/streamlit/streamlit_pdf_link.py) temp static files.
- **Idempotency**: surface duplicate-key and content-hash conflicts as **409 Conflict** with a clear body, matching behaviors in [`02-domain-rules-and-formats.md`](02-domain-rules-and-formats.md).

---

## Health / config

| Method | Path | Notes |
|--------|------|--------|
| GET | `/health` | Liveness |
| GET | `/ready` | DB reachable; optional LLM key present |

---

## NFs (`/nfs`)

| Method | Path | Body | Behavior |
|--------|------|------|----------|
| POST | `/nfs/parse-preview` | multipart `file` (PDF) | Run `parse_nf_pdf` + `compute_brl`; no DB write |
| POST | `/nfs` | multipart: PDF + `fiscal_mes` + optional multiple `images[]` | `save_pdf` + `save_nf_entry` + images; 409 on duplicate NF |
| GET | `/nfs` | query `date_from`, `date_to` and/or `fiscal_mes` | `get_nf_entries` |
| GET | `/nfs/{id}` | | `get_nf_by_id` |
| PATCH | `/nfs/{id}` | JSON `{ "fiscal_mes": "YYYY-MM" }` | `update_nf_fiscal_mes` |
| DELETE | `/nfs/{id}` | | `delete_nf` |
| GET | `/nfs/{id}/pdf` | | stream PDF bytes |
| GET | `/nfs/{id}/images` | | list `get_nf_images` |
| GET | `/nfs/{id}/images/{image_id}` | | stream file |

---

## Boletos (`/boletos`)

| Method | Path | Body | Behavior |
|--------|------|------|----------|
| POST | `/boletos/parse-preview` | PDF | `parse_boleto_pdf` |
| POST | `/receipts/parse-preview` | image | `parse_receipt_image` (shared with DARF) |
| POST | `/boletos` | multipart PDF + `fiscal_mes` + optional receipt image + receipt metadata | save chain; 409 on duplicate hash |
| GET | `/boletos` | `fiscal_mes` optional | `get_boletos` |
| GET | `/boletos/{id}` | | `get_boleto_by_id` |
| PATCH | `/boletos/{id}` | JSON `{ "fiscal_mes" }` | `update_boleto_fiscal_mes` |
| PUT | `/boletos/{id}/pdf` | PDF | `update_boleto_pdf` |
| PUT | `/boletos/{id}/receipt` | image + dates | `update_boleto_receipt` |
| DELETE | `/boletos/{id}` | | `delete_boleto` |
| GET | `/boletos/{id}/pdf` | | download |
| GET | `/boletos/{id}/receipt` | | download image |

Optional: `GET /boletos/{id}/barcode-diff` returning text from `format_barcode_diff` when `receipt_match_status == mismatch`.

---

## DARFs (`/darfs`)

Mirror boletos with `parse_darf_pdf` and DARF persistence functions — same verb shapes as `/boletos`.

---

## Extratos (`/extratos`)

| Method | Path | Body | Behavior |
|--------|------|------|----------|
| POST | `/extratos/parse-preview` | multipart: `extrato` PDF, optional `caixinha`, optional `higlobe` | run parsers; no save; may return errors for LLM failure |
| POST | `/extratos` | same + `fiscal_mes` | `save_extrato_entry` + PDFs; 409 on duplicate period hash |
| GET | `/extratos` | `fiscal_mes` optional | `get_extratos` |
| GET | `/extratos/{id}` | | `get_extrato_by_id` |
| PATCH | `/extratos/{id}` | `{ "fiscal_mes" }` | `update_extrato_fiscal_mes` |
| PUT | `/extratos/{id}/extrato-pdf` | PDF | `update_extrato_pdf` |
| PUT | `/extratos/{id}/caixinha` | PDF | `update_caixinha_pdf` |
| DELETE | `/extratos/{id}/caixinha` | | `remove_caixinha_pdf` |
| PUT | `/extratos/{id}/higlobe` | PDF | `update_higlobe_pdf` |
| DELETE | `/extratos/{id}/higlobe` | | `remove_higlobe_pdf` |
| DELETE | `/extratos/{id}` | | `delete_extrato` |
| GET | `/extratos/{id}/.../file` | | download each stored PDF |

---

## Fiscal months (`/fiscal-months`)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/fiscal-months` | List distinct months (union logic from [`7_Mês_Fiscal.py`](../../src/pjtracker/streamlit/pages/7_Mês_Fiscal.py)) |
| GET | `/fiscal-months/{yyyy-mm}/completeness` | Returns counts + booleans for NF/boleto/DARF/extrato/Higlobe rules |

---

## Analytics

| Method | Path | Query | Notes |
|--------|------|-------|--------|
| GET | `/analytics/nf-series` | `date_from`, `date_to` | Points per [`04-operations-by-domain.md`](04-operations-by-domain.md) Analytics section |

---

## File serving strategy

1. **Preferred**: authenticated GET by entity id + asset role; read path from DB, resolve relative to app-configured **storage root** (project root today).
2. **Alternative**: signed URLs if storage moves to object storage; DB still stores logical or relative paths.

Do **not** rely on `src/pjtracker/static/temp` from [`open_pdf_link`](../../src/pjtracker/streamlit/streamlit_pdf_link.py) in production.
