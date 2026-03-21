# Parsers and extraction

Convention: primary input is **`pdf_bytes: bytes`** and optional **`filename: str`** for LLM prompts / logging.

## Nota Fiscal — [`src/pjtracker/parsers/nf_parser.py`](../../src/pjtracker/parsers/nf_parser.py)

### Entry point

- `parse_nf_pdf(pdf_bytes, filename="nota_fiscal.pdf")` → **`NFParsed`**

### `NFParsed` fields

| Field | Meaning |
|-------|---------|
| `company` | |
| `usd`, `rate` | Parsed amounts; both needed for downstream BRL |
| `spread` | Default **3.0** if not found (`DEFAULT_SPREAD`); `spread_was_default` tracks that |
| `nf_date` | e.g. `DD/MM/YYYY HH:MM:SS` |
| `verification_code` | Line after `"Código de Verificação"` in PDF text, or LLM |
| `payment_via` | `Higlobe` / `Wise` / `None` from text or LLM |
| `source` | `"llm"` \| `"merged"` \| `"fallback"` — merge rules when LLM partial + text fallback |

### Pipeline

1. `extract_nf_pdf()` from [`src/pjtracker/llm_extraction.py`](../../src/pjtracker/llm_extraction.py).
2. `_parse_nf_pdf_with_text()` — `pypdf` text extraction, description block between markers or Código de Verificação section, `parse_description_block()` for USD/rate/spread/company.

### BRL

- `compute_brl(usd, rate, spread)` → `BRLResult(brl_no_spread, brl_with_spread)` — see [`02-domain-rules-and-formats.md`](02-domain-rules-and-formats.md).

### Other helpers

- `extract_text_from_pdf`, `get_verification_code`, `get_payment_via`, `get_date_from_pdf`, etc.

---

## Boleto PDF — [`src/pjtracker/parsers/boleto_parser.py`](../../src/pjtracker/parsers/boleto_parser.py)

### Entry point

- `parse_boleto_pdf(pdf_bytes, filename="boleto.pdf")` → **`BoletoParsed`**

### `BoletoParsed`

| Field | Meaning |
|-------|---------|
| `value` | BRL |
| `emission_date`, `deadline_date` | `DD/MM/YYYY` |
| `codigo_barras_raw` | from LLM |
| `codigo_barras_digits` | `normalize_digits(raw)` |
| `source` | `"llm"` \| `"merged"` \| `"fallback"` |

### Pipeline

1. `extract_boleto_pdf()` (LLM, Pydantic `BoletoPdfExtraido` in `llm_extraction`).
2. `_parse_boleto_pdf_with_ocr()` — EasyOCR on PDF pages via `pdf2image`, regex for value/dates.

---

## Receipt image (boleto + DARF) — [`src/pjtracker/parsers/boleto_parser.py`](../../src/pjtracker/parsers/boleto_parser.py)

### Entry point

- `parse_receipt_image(image_bytes, filename=..., mime_type=...)` → **`ReceiptParsed`**

### `ReceiptParsed`

| Field | Meaning |
|-------|---------|
| `value` | BRL |
| `payment_datetime` | normalized `DD/MM/YYYY HH:MM:SS` |
| `codigo_barras_raw`, `codigo_barras_digits` | |
| `source` | `"llm"` \| `"merged"` \| `"fallback"` |

### Pipeline

1. `extract_boleto_receipt()` — LLM with `ComprovanteExtraido`.
2. OCR fallback: `receipt_text_extractor` (top third of image), `parse_receipt_date_from_text` for `DD MMM YYYY - HH:MM:SS` patterns.

---

## DARF PDF — [`src/pjtracker/parsers/darf_parser.py`](../../src/pjtracker/parsers/darf_parser.py)

### Entry point

- `parse_darf_pdf(pdf_bytes, filename="darf.pdf")` → **`DarfParsed`**

### `DarfParsed`

| Field | Meaning |
|-------|---------|
| `value` | Total documento (BRL) |
| `emission_date` | **Período de apuração** — **`MM/YYYY`** |
| `deadline_date` | `DD/MM/YYYY` |
| `codigo_barras_raw`, `codigo_barras_digits` | |
| `source` | |

### Pipeline

- LLM `extract_darf_pdf` + OCR/text fallbacks shared with boleto text path where applicable (`boleto_text_extractor` import) — see file for regex and month-name normalization.

---

## Extrato / Caixinha / Higlobe — [`src/pjtracker/parsers/extrato_parser.py`](../../src/pjtracker/parsers/extrato_parser.py)

All three are **LLM-only** success paths: if `llm_data is None`, `parse_*` raises **`RuntimeError`** with message from `LLMExtractionResult.error`.

### `parse_extrato_pdf` → `ExtratoParsed`

- `entries`: `list[dict]` with keys `data`, `nome`, `descricao`, `valor`, `tipo` (normalized).
- `period_start` / `period_end`: inferred from entry dates via `_infer_period()` if not solely from model.
- `saldo_inicial`, `rendimento`, `total_entradas`, `total_saidas`, `saldo_final`, `source` (typically `"llm"`).

### `parse_caixinha_pdf` → `CaixinhaParsed`

- `entries`: keys include `data`, `movimentacao`, `rendimento`, `valor_bruto`, `imposto`, `iof`, `valor_liquido`.
- `saldo_final`, `period_start` / `period_end` (inferred).

### `parse_higlobe_pdf` → `HiglobeParsed`

- `entries`: keys `date`, `type`, `description`, `amount`, `currency`.
- Period from `_infer_period_higlobe()` using embedded `DD/MM/YYYY` in date strings.

---

## LLM layer — [`src/pjtracker/llm_extraction.py`](../../src/pjtracker/llm_extraction.py)

- **Auth**: `MARITACA_API_KEY` or `.token` file; **base URL** `MARITACA_BASE_URL`; **model** `MARITACA_MODEL`.
- **Client**: `_get_client()` — raises if no API key configured (Portuguese error message).
- **Structured output**: Pydantic models e.g. `BoletoPdfExtraido`, `ComprovanteExtraido`, `DarfPdfExtraido`, NF model(s), extrato schemas — see file.
- **Helpers**: `normalize_digits`, `normalize_dd_mm_yyyy`, `normalize_payment_datetime`, `normalize_payment_via`, etc.

## Tests

Parser merge behavior and normalization are covered in [`tests/test_refactor.py`](../../tests/test_refactor.py).
