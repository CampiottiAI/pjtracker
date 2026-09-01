# Frontend Integration Guide

This document is for frontend engineers integrating with the FastAPI app in `src/pjtracker/api/`.

The goal is not just to list routes, but to explain how the API behaves so you can design forms, request flows, optimistic updates, error states, and file-download actions without reading the backend code first.

## Quick start

Install dependencies:

```bash
uv sync
```

Run the API from the project root:

```bash
uv run uvicorn pjtracker.api.main:app --reload
```

Useful local URLs:

- API base: `http://127.0.0.1:8000/api/v1`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

Swagger is the fastest way to inspect the exact live request and response schema while building the frontend. This guide explains how to think about the API at the product-flow level.

## What the frontend needs to know first

### No auth yet

There is currently no authentication or authorization layer in `src/pjtracker/api/main.py`. Frontend requests do not need tokens or session headers today.

### Two kinds of routes

Most upload domains follow the same pattern:

- `parse-preview` routes: inspect uploaded files, return extracted metadata, and do not save anything
- create routes (`POST` to a collection): save files plus a database row
- update routes (`PUT`/`PATCH`): update one part of an existing saved record
- download routes (`GET` on `/pdf`, `/receipt`, etc.): return binary files

For a UI, the normal flow should be:

1. User selects file(s).
2. Frontend calls a preview endpoint.
3. UI shows extracted values and possible warnings.
4. User confirms.
5. Frontend calls the create endpoint.

### Content types

The API uses two request styles:

- `application/json` for simple patch operations like updating `fiscal_mes`
- `multipart/form-data` for anything involving PDFs or images

### Dates and field formats

Important formats the frontend should respect:

- `fiscal_mes`: `YYYY-MM`
- analytics dates: `YYYY-MM-DD`
- receipt form fields are passed as strings, and the backend expects frontend values shaped like `receipt_date=YYYY-MM-DD` and `receipt_time=HH:MM:SS`

### Binary downloads

Routes such as `/pdf`, `/receipt`, `/images/{image_id}`, `/extrato-pdf`, `/caixinha-pdf`, and `/higlobe-pdf` return file responses, not JSON.

In a browser client, treat them as downloads or open them in a new tab using a blob/object URL.

### Stored rows are mostly raw database rows

List/get/create responses for saved entities are mostly direct database rows converted to JSON dictionaries. That matters because:

- field names are storage-oriented, not presentation-oriented
- file paths such as `pdf_path` or `receipt_path` may appear in JSON, but the frontend should prefer the dedicated download routes instead of using those paths directly
- some fields are nullable and may be absent until a secondary file is uploaded
- extrato entry arrays are persisted as JSON strings in fields like `extrato_entries_json`, `caixinha_entries_json`, and `higlobe_entries_json`

Preview routes are usually cleaner and more structured than the saved-row responses.

## Cross-cutting frontend behavior

### Error handling

You should explicitly handle these statuses in the UI:

- `404`: record or file does not exist
- `422`: validation problem, empty file, invalid `fiscal_mes`, bad date range, or parsing failure
- `409`: duplicate or conflicting content

Important detail: conflict responses use a nested body shape:

```json
{
  "detail": {
    "detail": "A nota fiscal with the same date, verification code, and USD already exists.",
    "code": "duplicate_nf",
    "existing_id": 12
  }
}
```

So in the client, do not assume `error.detail` is always a string. It may be an object with:

- `code`
- `detail`
- optional extra keys such as `existing_id`

### `PATCH` behavior for fiscal month

All major entities support:

- `PATCH /.../{id}` with JSON body `{ "fiscal_mes": "2025-03" }`
- clearing the value with `{ "fiscal_mes": null }`

This is useful for inline editing in tables or detail screens.

### Recommended client helpers

For a web app, a small wrapper around `fetch()` is enough.

JSON request:

```ts
const API_BASE = "http://127.0.0.1:8000/api/v1";

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw { status: response.status, body: errorBody };
  }
  return response.json() as Promise<T>;
}
```

Multipart upload:

```ts
async function apiForm<T>(path: string, form: FormData, method = "POST"): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    body: form,
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw { status: response.status, body: errorBody };
  }
  return response.json() as Promise<T>;
}
```

Binary download:

```ts
async function downloadFile(path: string, filename?: string) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(`Download failed with ${response.status}`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename ?? "";
  a.click();
  URL.revokeObjectURL(url);
}
```

## Health and capability checks

### `GET /health`

Use this for a simple liveness check.

Response:

```json
{ "status": "ok" }
```

### `GET /ready`

Use this if the frontend wants to show whether the backend is fully usable.

Response shape:

```json
{
  "ready": true,
  "database": true,
  "llm_key_configured": true,
  "token_file_exists": true
}
```

Practical meaning:

- `database=false`: the API is up but cannot reach SQLite correctly
- `llm_key_configured=false`: upload routes that depend on LLM-backed parsing may fail or be partially unusable

## NFs

### What this domain does

NFs are the cleanest upload flow:

- preview parses one NF PDF
- create saves the PDF plus optional image attachments
- list/get return raw NF rows
- images are fetched through separate endpoints

### Frontend flow

Recommended UI:

1. Let the user upload one NF PDF.
2. Call `POST /nfs/parse-preview`.
3. Show parsed fields such as company, USD, rate, spread, BRL totals, date, and verification code.
4. Let the user choose `fiscal_mes`.
5. Optionally let the user attach multiple images.
6. Call `POST /nfs`.

### Preview route

`POST /nfs/parse-preview`

Form fields:

- `file`: required PDF

Frontend expectation:

- response is parsed metadata
- no database row is created
- BRL computation is included when `usd` and `rate` were extracted successfully

Example response:

```json
{
  "company": "Acme",
  "usd": 100.0,
  "rate": 5.2,
  "spread": 3.0,
  "spread_was_default": false,
  "nf_date": "15/03/2025 12:00:00",
  "verification_code": "XYZ",
  "payment_via": "Higlobe",
  "source": "test",
  "brl": {
    "brl_no_spread": 520.0,
    "brl_with_spread": 504.4
  }
}
```

### Create route

`POST /nfs`

Form fields:

- `file`: required PDF
- `fiscal_mes`: required `YYYY-MM`
- `images`: optional repeated file field

Important frontend detail:

- append each attachment under the same `images` key in `FormData`

Example:

```ts
const form = new FormData();
form.append("file", nfPdf);
form.append("fiscal_mes", "2025-03");
attachments.forEach((file) => form.append("images", file));
const saved = await apiForm("/nfs", form);
```

### List/get responses

Saved NF rows include fields like:

- `id`
- `company`
- `usd`
- `rate`
- `spread`
- `brl_no_spread`
- `brl_with_spread`
- `nf_date`
- `verification_code`
- `payment_via`
- `pdf_path`
- `fiscal_mes`
- `created_at`

Routes:

- `GET /nfs`
- `GET /nfs/{nf_id}`

Filters:

- `GET /nfs?fiscal_mes=2025-03`
- `GET /nfs?date_from=2025-03-01&date_to=2025-03-31`

Behavior note:

- if `fiscal_mes` is present, the backend uses that filter path instead of the date range path

### Images

Routes:

- `GET /nfs/{nf_id}/images`
- `GET /nfs/{nf_id}/images/{image_id}`

Use `/images` to populate an attachments list in the UI, and `/images/{image_id}` to download or preview the selected file.

### Update and delete

Routes:

- `PATCH /nfs/{nf_id}`
- `DELETE /nfs/{nf_id}`

There is no NF PDF replacement route right now. Replacement would need a delete-and-recreate UX if the frontend wants to support it.

## Boletos

### What this domain does

Boletos have a two-file model:

- required boleto PDF
- optional receipt image

The backend also compares barcode digits between the boleto and the receipt when both are available.

### Frontend flow

Recommended UI:

1. User uploads boleto PDF.
2. Frontend calls `POST /boletos/parse-preview`.
3. Show parsed amount, emission date, due date, and barcode digits.
4. User chooses `fiscal_mes`.
5. Optionally upload a receipt image.
6. If uploading a receipt, provide a payment date/time input in the UI unless you are comfortable relying on OCR extraction.
7. Submit `POST /boletos`.

### Boleto preview

`POST /boletos/parse-preview`

Form fields:

- `file`: required PDF

Returns extracted boleto metadata only.

### Shared receipt preview

`POST /receipts/parse-preview`

Use this if you want to preview receipt OCR before saving a boleto or DARF.

Form fields:

- `file`: required image

Response shape:

```json
{
  "value": 250.0,
  "payment_datetime": "15/03/2025 14:35:00",
  "codigo_barras_raw": "...",
  "codigo_barras_digits": "...",
  "source": "ocr"
}
```

This is useful for showing the user whether the receipt looks valid before the final create/update request.

### Create boleto

`POST /boletos`

Form fields:

- `file`: required boleto PDF
- `fiscal_mes`: required
- `receipt`: optional image
- `receipt_date`: optional but strongly recommended when `receipt` is sent
- `receipt_time`: optional, defaults to `00:00:00` when `receipt_date` is provided without time

Important frontend rule:

- if `receipt` is provided and OCR cannot extract a payment datetime, the request fails with `422`
- the safest UI is to always collect `receipt_date` and optionally `receipt_time` whenever a receipt image is uploaded

### Saved boleto rows

List/get/create/update responses contain fields like:

- `id`
- `pdf_path`
- `receipt_path`
- `value`
- `emission_date`
- `deadline_date`
- `receipt_date`
- `codigo_barras`
- `codigo_barras_digits`
- `receipt_value`
- `receipt_codigo_barras`
- `receipt_codigo_barras_digits`
- `receipt_match_status`
- `content_hash`
- `fiscal_mes`
- `created_at`
- `updated_at`

Routes:

- `GET /boletos`
- `GET /boletos/{boleto_id}`
- `PATCH /boletos/{boleto_id}`
- `DELETE /boletos/{boleto_id}`

### Replacing files after creation

Routes:

- `PUT /boletos/{boleto_id}/pdf`
- `PUT /boletos/{boleto_id}/receipt`

Use these when the record already exists and the user wants to replace a file.

Frontend behavior to expect:

- replacing the PDF re-parses boleto fields and may change match status
- replacing the receipt deletes the old stored receipt file first
- replacing the PDF can fail with `409 duplicate_boleto_hash`

### Barcode mismatch UX

If `receipt_match_status === "mismatch"`, the frontend can show a "view diff" action using:

- `GET /boletos/{boleto_id}/barcode-diff`

This route returns plain text, not JSON.

Only call it when the status is `mismatch`; otherwise the backend returns `404`.

### Download routes

- `GET /boletos/{boleto_id}/pdf`
- `GET /boletos/{boleto_id}/receipt`

## DARFs

### What this domain does

DARFs behave almost exactly like boletos:

- required DARF PDF
- optional receipt image
- optional receipt date/time provided by the frontend
- barcode comparison and mismatch diff

### Frontend guidance

You can usually reuse the same UI components and API helpers as boletos, changing only the route prefix from `/boletos` to `/darfs`.

Routes:

- `POST /darfs/parse-preview`
- `POST /darfs`
- `GET /darfs`
- `GET /darfs/{darf_id}`
- `PATCH /darfs/{darf_id}`
- `PUT /darfs/{darf_id}/pdf`
- `PUT /darfs/{darf_id}/receipt`
- `DELETE /darfs/{darf_id}`
- `GET /darfs/{darf_id}/pdf`
- `GET /darfs/{darf_id}/receipt`
- `GET /darfs/{darf_id}/barcode-diff`

The same receipt rule applies here:

- if a receipt image is uploaded, the safest UI is to also send `receipt_date`

## Extratos

### What this domain does

Extratos are the most complex upload flow. A record can have:

- one required main statement PDF: `extrato`
- one optional `caixinha` PDF
- one optional `higlobe` PDF

### Important difference between preview and saved responses

Preview response:

- nested and parser-oriented
- easier for frontend confirmation screens

Saved response:

- flat database row
- parsed entry arrays are stored in JSON string columns

That means a frontend should treat preview and persisted data as different shapes.

### Frontend flow

Recommended UI:

1. User selects the main `extrato` PDF.
2. Optionally selects `caixinha` and `higlobe`.
3. Frontend calls `POST /extratos/parse-preview`.
4. UI shows period, balances, totals, and whether optional files parsed successfully.
5. User chooses `fiscal_mes`.
6. Frontend calls `POST /extratos`.

### Preview route

`POST /extratos/parse-preview`

Form fields:

- `extrato`: required PDF
- `caixinha`: optional PDF
- `higlobe`: optional PDF

Response shape:

```json
{
  "extrato": {
    "period_start": "2025-03-01",
    "period_end": "2025-03-31",
    "saldo_inicial": 1000.0,
    "rendimento": 25.0,
    "total_entradas": 400.0,
    "total_saidas": 200.0,
    "saldo_final": 1225.0,
    "entries": [],
    "source": "parser"
  },
  "caixinha": null,
  "higlobe": null
}
```

Frontend implication:

- render each section independently because `caixinha` and `higlobe` may be `null`

### Create route

`POST /extratos`

Form fields:

- `extrato`: required PDF
- `fiscal_mes`: required
- `caixinha`: optional PDF
- `higlobe`: optional PDF

Possible failure modes:

- parse/runtime failure: `422`
- duplicate period: `409 duplicate_extrato`

### Saved extrato rows

The stored row includes fields like:

- `id`
- `extrato_pdf_path`
- `caixinha_pdf_path`
- `higlobe_pdf_path`
- `period_start`
- `period_end`
- `saldo_inicial`
- `rendimento`
- `total_entradas`
- `total_saidas`
- `saldo_final`
- `caixinha_saldo_final`
- `extrato_entries_json`
- `caixinha_entries_json`
- `higlobe_entries_json`
- `content_hash`
- `fiscal_mes`
- `created_at`
- `updated_at`

Frontend implication:

- if you need actual arrays for rendering, parse `extrato_entries_json`, `caixinha_entries_json`, and `higlobe_entries_json` on the client

### Update routes

Routes:

- `PATCH /extratos/{extrato_id}`
- `PUT /extratos/{extrato_id}/extrato-pdf`
- `PUT /extratos/{extrato_id}/caixinha`
- `DELETE /extratos/{extrato_id}/caixinha`
- `PUT /extratos/{extrato_id}/higlobe`
- `DELETE /extratos/{extrato_id}/higlobe`
- `DELETE /extratos/{extrato_id}`

Frontend behavior to expect:

- replacing the main PDF re-parses the extrato and can fail with `409 duplicate_extrato_period`
- adding or replacing `caixinha` and `higlobe` updates only those parts of the row
- deleting `caixinha` or `higlobe` returns `204`

### Download routes

- `GET /extratos/{extrato_id}/extrato-pdf`
- `GET /extratos/{extrato_id}/caixinha-pdf`
- `GET /extratos/{extrato_id}/higlobe-pdf`

Only show the `caixinha` and `higlobe` download actions when the corresponding `*_pdf_path` field is present.

## Fiscal months

### What this is for

This is a support domain for month-based UI dashboards and completeness views.

### List months

`GET /fiscal-months`

Response:

```json
{
  "months": ["2025-04", "2025-03", "2025-02"]
}
```

Use this to populate a month picker or dashboard filter.

### Check month completeness

`GET /fiscal-months/{fiscal_mes}/completeness`

Response fields:

- `fiscal_mes`
- `nfs_count`
- `nfs_ok`
- `boletos_with_receipt_count`
- `boletos_ok`
- `darfs_with_receipt_count`
- `darfs_ok`
- `extratos_caixinha_count`
- `extratos_ok`
- `extratos_higlobe_count`
- `higlobe_ok`
- `month_complete`

This is useful for:

- a month status card
- checklist badges
- blocking or warning before finalization workflows

Validation note:

- invalid month format returns `422`

### Download month document pack

`GET /fiscal-months/{fiscal_mes}/pack`

Returns a zip archive (`application/zip`) with all documents for the fiscal month:

- NF PDFs and their associated images (`nfs/`)
- Extrato, caixinha, and higlobe PDFs when present (`extratos/`)

Zip layout example:

```text
nfs/nf_{id}_{verification_code}.pdf
nfs/nf_{id}_{verification_code}_img_{image_id}.png
extratos/extrato_{id}.pdf
extratos/caixinha_{id}.pdf
extratos/higlobe_{id}.pdf
```

Response headers include `Content-Disposition: attachment; filename="documents_pj_{fiscal_mes}.zip"`.

Errors:

- `422` when `fiscal_mes` is not `YYYY-MM`
- `404` when no readable files exist for that month

Boletos, DARFs, and IRPJ/CSLL are not included in the pack.

## Analytics

### NF series

`GET /analytics/nf-series?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD`

This route returns chart-ready points derived from saved NF entries.

Response shape:

```json
{
  "points": [
    {
      "date": "2025-03-10",
      "usd": 20.0,
      "brl_no_spread": 100.0,
      "brl_with_spread": 100.0,
      "rate": 5.0,
      "spread": 0.0,
      "effective_rate": 5.0
    }
  ]
}
```

Frontend use cases:

- line charts
- BRL/USD comparison charts
- rate and effective rate overlays

Validation note:

- if `date_from > date_to`, the route returns `422`

## Suggested screen-level mapping

If you are designing the frontend from scratch, this API maps cleanly to these screens:

- health/status screen: `GET /health`, `GET /ready`
- NF upload screen: `POST /nfs/parse-preview`, then `POST /nfs`
- NF list/detail screen: `GET /nfs`, `GET /nfs/{id}`, `GET /nfs/{id}/images`
- boleto upload screen: `POST /boletos/parse-preview`, optional `POST /receipts/parse-preview`, then `POST /boletos`
- boleto detail screen: `PUT /boletos/{id}/pdf`, `PUT /boletos/{id}/receipt`, `GET /boletos/{id}/barcode-diff`
- DARF screens: same pattern as boletos under `/darfs`
- extrato upload screen: `POST /extratos/parse-preview`, then `POST /extratos`
- extrato detail screen: optional attachment management with `/caixinha` and `/higlobe`
- month dashboard: `GET /fiscal-months`, `GET /fiscal-months/{month}/completeness`
- analytics page: `GET /analytics/nf-series`

## Practical gotchas

- Do not hardcode direct file paths from JSON responses into the frontend. Use the download routes.
- Do not assume all errors return the same JSON shape. `409` is structured differently.
- Do not rely on receipt OCR alone if the UX can easily capture payment date/time.
- Do not assume extrato saved responses contain parsed arrays as arrays; they are stored in JSON string fields.
- Do not call barcode diff routes unless the saved row says the match status is `mismatch`.
- Do not expect all create/update flows to return the same semantic shape as preview flows.

## Minimum frontend contract by domain

If you only need the shortest possible implementation checklist:

- NFs: upload PDF, preview, choose `fiscal_mes`, optionally upload repeated `images`
- boletos: upload PDF, choose `fiscal_mes`, optionally upload `receipt`, preferably send `receipt_date`
- DARFs: same as boletos
- extratos: upload required `extrato`, optional `caixinha` and `higlobe`, preview before create
- fiscal months: use list plus completeness endpoints for dashboard/status UI
- analytics: send date range and render returned `points`
