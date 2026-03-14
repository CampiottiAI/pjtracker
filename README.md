# pjtracker

Company management tools for Brazil. Currently includes a **Nota Fiscal tracker** that extracts and validates data from NF-e PDFs (Campinas).

## Setup

```bash
uv sync
```

## Nota Fiscal Tracker

Upload a PDF of a Nota Fiscal (NF-e). The app will:

- Extract the service description block (between the CNAE/CBO description header and "TRIBUTAÇÃO MUNICIPAL")
- Parse **Company**, **USD value**, **conversion rate**, and **spread** (default 3% if not stated)
- Compute BRL with and without spread
- Compare the result to **Valor Líquido da NFSe Campinas (R$)** from the PDF

### Run the app

```bash
uv run streamlit run src/NFs.py
```

Then open the URL shown in the terminal (usually http://localhost:8501).
