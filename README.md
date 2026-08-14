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

### Dev (both servers)

From the repo root:

```bash
./scripts/dev.sh
```

Starts FastAPI with reload and the Vite dev server. Bind address defaults to `0.0.0.0` (`DEV_HOST`).

## Production (Pi / LAN)

For lower memory use on a Raspberry Pi or other LAN host, use the production script. It builds the frontend once and runs uvicorn (no reload) plus Vite preview (no HMR):

```bash
uv sync
cd frontend && npm install && cd ..
./scripts/prod.sh
```

Open `http://<machine-ip>:4173` (default). Environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PROD_HOST` | `0.0.0.0` | Preview bind address |
| `PROD_PORT` | `4173` | Preview port |
| `API_PORT` | `8000` | Internal uvicorn port |
| `PROD_BUILD` | `0` | Set to `1` to force a frontend rebuild on startup |
| `PJTRACKER_OCR` | `1` | Set to `0` to skip local EasyOCR (LLM-only parsing) |

On a 4GB Pi, prefer `./scripts/prod.sh` over dev mode. If uploads still struggle, try `PJTRACKER_OCR=0` when Maritaca LLM extraction is reliable, and consider adding swap.

## Backup (Google Drive via rclone)

Backs up the durable data only: `pjtracker.db`, `pdfs/`, and `images/`. Secrets (`.token`, SMTP env) are **not** included — keep those separately.

Requires: `sqlite3`, `tar`, and [`rclone`](https://rclone.org/) (for upload).

### One-time rclone setup

```bash
rclone config
# Storage: Google Drive
# remote name: gdrive
# scope: drive.file (files created by rclone) or drive
```

On a headless Pi, authorize on a machine with a browser (`rclone authorize "drive"`) and paste the token into the Pi config.

```bash
rclone lsd gdrive:
```

### Run backup

```bash
./scripts/backup.sh --dry-run      # build tar.gz locally, no upload
./scripts/backup.sh --local-only   # keep tar.gz locally, skip rclone
./scripts/backup.sh                # snapshot → tar.gz → upload → prune
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `RCLONE_REMOTE` | `gdrive` | rclone remote name |
| `RCLONE_PATH` | `pjtracker-backups` | folder on the remote |
| `KEEP_N` | `14` | how many remote tars to keep (`0` = no prune) |
| `KEEP_LOCAL` | `0` | set to `1` to keep the local tar after upload |
| `PJTRACKER_DB_PATH` | `<repo>/pjtracker.db` | override DB (pdfs/images live next to it) |

Cron example (daily 03:00):

```cron
0 3 * * * cd /path/to/pjtracker && ./scripts/backup.sh >> /tmp/pjtracker-backup.log 2>&1
```

### Restore

1. Stop the service.
2. Download: `rclone copy gdrive:pjtracker-backups/<file>.tar.gz .`
3. Extract at the repo root (overwrites `pjtracker.db`, `pdfs/`, `images/`): `tar -xzf pjtracker-YYYYMMDD-HHMMSS.tar.gz`
4. Start again with `./scripts/prod.sh`.

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
