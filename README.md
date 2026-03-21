# pjtracker

Company management tools for Brazil. Currently includes a **Nota Fiscal tracker** that extracts and validates data from NF-e PDFs (Campinas).

## Setup

```bash
uv sync
```

## API (FastAPI)

```bash
uv run uvicorn pjtracker.api.main:app --reload
```

- Base URL: `http://127.0.0.1:8000/api/v1`
- Docs: [docs/api/README.md](docs/api/README.md)

## Frontend (SvelteKit)

The web UI lives in [`frontend`](frontend). Use Node/npm there; Python tooling stays on `uv` at the repo root.

```bash
cd frontend
npm install
npm run dev
```

Run the FastAPI server in another terminal (see above). See [`frontend/README.md`](frontend/README.md) for env vars and the dev proxy.

## Nota Fiscal Tracker

Upload a PDF of a Nota Fiscal (NF-e). The app will:

- Extract the service description block (between the CNAE/CBO description header and "TRIBUTAÇÃO MUNICIPAL")
- Parse **Company**, **USD value**, **conversion rate**, and **spread** (default 3% if not stated)
- Compute BRL with and without spread
- Compare the result to **Valor Líquido da NFSe Campinas (R$)** from the PDF

### Run the app

```bash
uv run streamlit run src/pjtracker/streamlit/NFs.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).
