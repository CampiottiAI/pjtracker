# pjtracker — System Overview

## The Problem

Running a PJ (Pessoa Jurídica) in Brazil means dealing with a recurring pile of fiscal
documents every month: notas fiscais, boletos, DARFs, bank statements, and payment receipts.
Each document type has its own format, its own deadlines, and its own quirks. Missing a
single one means an incomplete fiscal month — and potential headaches with accounting.

The real pain points:

1. **Manual data entry is slow and error-prone.** Every nota fiscal contains USD amounts,
   exchange rates, and spread percentages buried inside PDF text. Extracting and computing
   BRL values by hand invites mistakes.

2. **Receipts must match their boletos.** When you pay a boleto, the payment receipt has a
   barcode that should match the original document. Verifying this manually is tedious.

3. **There's no single place to see what's done and what's missing.** Each fiscal month
   requires a specific set of documents (at least 2 NFs, 1 boleto with receipt, 1 DARF with
   receipt, 1 bank statement with caixinha). Without a tracker, you rely on memory or
   spreadsheets.

4. **Bank statements come in multiple flavors.** The main extrato, the "caixinha" (savings),
   and Higlobe (foreign currency) are separate PDFs that all belong to the same fiscal month
   but need to be parsed and stored together.

pjtracker solves this by providing a single web interface where you upload PDFs, the system
extracts the data automatically (via LLM-powered OCR), and a dashboard tells you exactly
what's complete and what's missing for each fiscal month.

---

## The Frontend

The frontend is a **SvelteKit** application living in the `frontend/` directory. It is the
primary interface to the system — all user interaction happens here.

### Tech Stack

| Layer | Technology |
|---|---|
| Framework | SvelteKit with Svelte 5 (runes) |
| Build tool | Vite 7 |
| Styling | Tailwind CSS 4 (dark theme by default) |
| UI primitives | bits-ui (Dialog, Sheet, Tabs, etc.) |
| Icons | lucide-svelte |
| Charts | Unovis (@unovis/svelte) |
| Toasts | svelte-sonner |
| API communication | Thin fetch wrapper (`$lib/api/client.ts`) |

The dev server proxies `/api` requests to the FastAPI backend at `localhost:8000` via Vite's
built-in proxy.

### Pages and Routes

```
/                 Fluxo (casa + saques + empresa)
/casa             Household bills split
/carros           Cars + maintenance quotes
/documentos       Document hub
/nfs              Notas Fiscais
/boletos          Boletos
/darfs            DARFs
/extratos         Bank Statements
/analytics        NF time-series charts
```

All data loading is **client-side** — there are no `+page.server.ts` files. State is managed
with Svelte 5 runes (`$state`, `$derived`, `$effect`) locally within each page; there is no
global store.

---

### Dashboard (`/`)

The entry point. You pick a **fiscal month** from a dropdown and immediately see a
completeness overview:

- **Notas Fiscais** — count vs. required (2)
- **Boletos c/ Recibo** — count vs. required (1)
- **DARFs c/ Recibo** — count vs. required (1)
- **Extratos c/ Caixinha** — count vs. required (1)
- **Higlobe** — count vs. required (1, optional)

Each card is a link that navigates to the corresponding page pre-filtered by that fiscal
month. A green/amber banner at the top tells you whether the month is complete.

---

### Notas Fiscais (`/nfs`)

Manages NF-e (Nota Fiscal de Serviço Eletrônica) documents. These are invoices issued for
services rendered, typically denominated in USD with a BRL conversion.

**Table columns:** date, company, USD, rate, spread, BRL (no spread / with spread), fiscal
month.

**Upload flow:**
1. Click "+ New NF" — a side sheet opens.
2. Drop a PDF into the file zone. The system sends it to the backend for parsing.
3. A preview appears showing extracted fields: company, USD value, exchange rate, spread
   percentage, and computed BRL amounts.
4. Pick a fiscal month, optionally attach images (e.g., screenshots of payments).
5. Save. The NF appears in the table.

**Detail view:** Click any row to open a detail sheet with full NF data. From here you can:
- Download or replace the PDF.
- View, add, or delete attached images.
- Edit the fiscal month inline.
- Delete the NF (with confirmation dialog).

**Filters:** Fiscal month dropdown, optional date-from / date-to range.

---

### Boletos (`/boletos`) and DARFs (`/darfs`)

These two pages share the same component (`BoletoLikePage`) with different API functions
injected as props. Boletos are payment slips (utility bills, rent, services); DARFs are
federal tax payment documents.

**Table columns:** value (BRL), emission date, deadline, receipt status, fiscal month.

**Upload flow:**
1. Drop the boleto/DARF PDF — the system parses value, dates, and barcode.
2. Optionally attach a payment receipt (image or PDF) with date and time.
3. The receipt is also parsed: value, payment datetime, barcode.
4. If the receipt barcode matches the document barcode, the status is "match". Otherwise it
   flags a "mismatch".
5. Pick a fiscal month and save.

**Detail view:**
- Download or replace the document PDF.
- Upload or replace the receipt.
- When there's a barcode mismatch, a diff view highlights the discrepancy.
- Edit fiscal month inline, delete with confirmation.

**Receipt matching** is a key feature: the system automatically compares the barcode on the
original boleto/DARF with the barcode on the payment receipt to confirm the right document
was paid.

---

### Bank Statements (`/extratos`)

Manages monthly bank statements, which can include up to three PDFs per entry:

| PDF | Description |
|---|---|
| **Extrato** | Main bank statement (required) |
| **Caixinha** | Savings/investment pocket statement |
| **Higlobe** | Foreign currency (USD) account statement |

**Upload flow:**
1. Drop the main extrato PDF (required). Optionally add caixinha and/or higlobe PDFs.
2. The system parses each: period, balances, individual entries.
3. A tabbed preview shows parsed data for each document type.
4. Pick a fiscal month and save.

**Detail view:**
- Summary with period, saldo inicial/final, rendimento, entradas, saídas.
- Tables of individual parsed entries for extrato, caixinha, and higlobe.
- Replace or remove any of the three PDFs independently.

---

### Analytics (`/analytics`)

Time-series charts for NF data over a configurable date range. Three charts:

1. **USD over time** — invoice amounts in dollars.
2. **BRL comparison** — BRL without spread vs. BRL with spread, showing the cost of
   currency conversion.
3. **Exchange rate** — official rate vs. effective rate (after spread), visualizing how much
   the intermediary markup costs.

Built with Unovis (`VisLine`, `VisAxis`, `VisCrosshair`, `VisTooltip`) in a shared `AnalyticsLineChart` component.

---

### Shared Components

| Component | Purpose |
|---|---|
| `Navbar` | Top navigation with links to all pages, API health indicator (polls `/ready` every 30s), mobile hamburger menu |
| `PageHeader` | Page title + description + optional action slot |
| `FiscalMonthPicker` | Dropdown bound to the list of fiscal months from the API, with manual text input fallback |
| `FileDropZone` | Drag-and-drop file upload area with loading state |
| `StatusBadge` | Color-coded badge (success/warning/error) with icon |
| `ConfirmDialog` | Destructive-action confirmation modal |
| `BoletoLikePage` | Full page template reused by both Boletos and DARFs routes |

### UI Primitives

The project uses **bits-ui**-based components in `$lib/components/ui/`, following the
shadcn-svelte pattern: Button, Card, Dialog, Sheet, Input, Badge, Table, Tabs, Separator,
Skeleton, Sonner (toasts). All are styled with Tailwind CSS and support the dark theme
defined in `app.css`.

---

### API Client (`$lib/api/client.ts`)

A small, typed wrapper around `fetch`:

- `apiJson<T>(path, init?)` — GET/POST/PATCH/DELETE with JSON.
- `apiForm<T>(path, form, method?)` — multipart uploads.
- `downloadBlob(path)` — binary downloads (PDFs, images).
- `ApiError` class with status and parsed body for structured error handling.
- One function per endpoint (e.g., `createNf`, `listBoletos`, `getCompleteness`), keeping
  page components free of raw fetch logic.

### Formatting Utilities (`$lib/utils/format.ts`)

- `formatFiscalMes("2025-03")` → `"Março 2025"`
- `formatBrl(1234.56)` → `"R$ 1.234,56"`
- `formatUsd(1000)` → `"US$ 1,000.00"`
- `formatDateBr("2025-03-15")` → localized date string
- `formatNumber`, `formatPercent` for general numeric display

---

### Carros (`/carros`)

Own navbar tab (not part of Fluxo or Casa bills). Manage named cars and workshop quotes:

1. Select a car (or manage cars: name, placa, modelo).
2. Upload a quote (image/PDF) → Maritaca extract → edit header/vehicle/total → save.
3. On save, the API stores the file under `data/casa/maintenance/` and runs an analysis
   vs the previous visit for that car.
4. Detail view: documento, análise, anexos (images/PDFs/videos).

Not tied to fiscal months or completeness.

---

### Key Design Decisions

1. **Client-side only data loading.** No SSR data fetching — every page loads data in
   `onMount` or `$effect`. This keeps the SvelteKit layer stateless and avoids coupling to
   the backend at build time.

2. **Reusable page component for similar domains.** Boletos and DARFs have identical UI
   patterns, so `BoletoLikePage` accepts API functions as props instead of duplicating the
   page.

3. **Fiscal month as the organizing axis.** Every document is tagged with a fiscal month
   (`YYYY-MM`). The dashboard, filters, and deep links all revolve around this concept.

4. **LLM-powered parsing as a first-class feature.** The upload flow always shows a parsed
   preview before saving, so the user can verify what the system extracted before committing.

5. **Dark theme by default.** The `<html>` element has `class="dark"` set in `app.html`.
   All color tokens are defined in `app.css` using Tailwind v4's `@theme` directive.
