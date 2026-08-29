# pjtracker

Company (PJ) fiscal document tracker for Brazil: upload PDFs, extract fields (LLM + OCR), store them, and see what is missing for each **fiscal month** (`YYYY-MM`).

Python ≥ 3.13 with **uv**. Frontend is a separate Node app in `frontend/` — see `frontend/AGENTS.md`. Product narrative: `SYSTEM.md`. API contract: `docs/api/README.md`. Domain/persistence: `docs/backend-migration/`.

## Run

```bash
uv sync
./scripts/dev.sh          # API + Vite, or two terminals:
uv run uvicorn pjtracker.api.main:app --reload   # http://127.0.0.1:8000
cd frontend && npm run dev                       # proxies /api → :8000
uv run pytest
```

Production (Pi/LAN): `./scripts/prod.sh`. Backup: `./scripts/backup.sh` (db + `pdfs/` + `images/` only). Deadline cron: `uv run pjtracker-check`.

## Layout

```
src/pjtracker/app.py           # SQLite schema, file paths, CRUD helpers (source of truth for persistence)
src/pjtracker/api/             # FastAPI: routers + thin services
src/pjtracker/parsers/         # PDF/image extraction per document type
src/pjtracker/llm_extraction.py
src/pjtracker/casa/          # Household split logic + JSON storage (data/casa/)
src/pjtracker/streamlit/       # Legacy Streamlit UI — do not extend; FastAPI + SvelteKit is the product
frontend/                      # SvelteKit UI
tests/                         # pytest (API smoke, parsers, checks)
docs/api/README.md
```

Package is src-layout (`pjtracker` under `src/`). Persistence paths are repo-root: `pjtracker.db`, `pdfs/`, `images/` (`PJTRACKER_DB_PATH` relocates all three).

## Stack

| Layer | Tech |
|-------|------|
| API | FastAPI, prefix `/api/v1`, no auth |
| DB | SQLite via stdlib; `init_db()` on API lifespan |
| Parse | Maritaca LLM (`MARITACA_API_KEY` or first line of `.token`) + EasyOCR/pdf2image |
| UI | SvelteKit 2 / Svelte 5 / Tailwind 4 / bits-ui — client-side fetch only |
| Checks | `pjtracker-check` CLI + optional Gmail SMTP |

Do not use pip / `python -m venv`. Frontend: npm in `frontend/` only.

## Domains

Upload flow is always **parse-preview (no save) → user confirms → create**. Multipart for files; JSON for patches like `fiscal_mes`.

| Area | Routes | Notes |
|------|--------|-------|
| NFs | `/nfs` | USD + rate + spread → BRL; Campinas NF-e |
| Boletos / DARFs | `/boletos`, `/darfs` | Same UI (`BoletoLikePage`); receipt barcode match |
| IRPJ/CSLL | `/irpj-csll` | Required on quarter-ending months (03/06/09/12) |
| Extratos | `/extratos` | Main PDF required; optional caixinha + Higlobe |
| Withdraws | `/withdraws` | BRL withdrawals per fiscal month |
| Casa | `/casa` | Household bills, split, month snapshots |
| Fluxo | `/fluxo` | Aggregated coverage (saques vs casa + empresa) |
| Fiscal months | `/fiscal-months` | Completeness: 2 NFs, 1 boleto+receipt, 1 DARF+receipt, 1 extrato+caixinha; Higlobe optional |
| Analytics | `/analytics` | NF time series |
| Health | `/ready` | Navbar polls this |

Routers stay thin: HTTP in `api/routers/`, completeness/path helpers in `api/services/`, DB+files in `app.py`, extraction in `parsers/`. List/get JSON is mostly raw DB rows — the UI should use download routes, not `pdf_path`.

## Checks CLI

`src/pjtracker/checks/registry.py` is the list of cron checks (pro-labore withdraw, previous-month DARF receipt). New checks: implement `DeadlineCheck`, register there, add tests in `tests/test_checks.py`.

## Do not

- Commit `.token`, `*.db`, `pdfs/`, `images/`, `pjtracker-*.tar.gz`.
- Add `+page.server.ts` / SSR data loading — pages load in `onMount` / `$effect`.
- Bypass parse-preview on new upload UIs.
- Call Maritaca/OCR in unit tests — mock parsers (`tests/test_api.py` pattern with temp DB paths).
- Treat Streamlit as the place for new features.
