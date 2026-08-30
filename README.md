# pjtracker

Company management tools for Brazil. Currently includes a **Nota Fiscal tracker** that extracts and validates data from NF-e PDFs (Campinas).

## Setup

```bash
uv sync
```

## Scripts

| Script | Purpose |
|--------|---------|
| [`./scripts/dev.sh`](#dev-both-servers) | FastAPI + Vite dev servers (reload / HMR). Bind: `DEV_HOST` (default `0.0.0.0`) |
| [`./scripts/prod.sh`](#production-pi--lan) | Build frontend, run uvicorn (no reload) + Vite preview. For Pi / LAN |
| [`./scripts/backup.sh`](#backup-google-drive-via-rclone) | Snapshot `pjtracker.db`, `pdfs/`, `images/` (optional rclone upload to Drive) |
| [`./scripts/restore.sh`](#restore) | Apply a `backup.sh` archive into the current folder (`pjtracker.db`, `pdfs/`, `images/`) |
| [`uv run python scripts/import_casa_data.py`](#import-casa-data) | Import household data from a casa project into `data/casa/` |
| [`uv run pjtracker-check`](#deadline-checks) | Fiscal deadline checks (pro-labore withdraw, previous-month DARF receipt); optional email |

`scripts/_common.sh` is sourced by `dev.sh` and `prod.sh` (Maritaca token, process cleanup). Do not run it directly.

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

Requires: `sqlite3` and `tar`. [`rclone`](https://rclone.org/) is only needed to upload; `--local-only` works without it and prints the archive path plus an `scp` command to fetch it.

### Install rclone (Pi)

Preferred (latest binary):

```bash
sudo apt update
sudo apt install -y curl unzip
curl https://rclone.org/install.sh | sudo bash
rclone version
```

Or from Debian packages (often older): `sudo apt install -y rclone`.

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
./scripts/backup.sh --clean-local  # delete local pjtracker-*.tar.gz (after scp)
./scripts/backup.sh                # snapshot → tar.gz → upload → prune
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `RCLONE_REMOTE` | `gdrive` | rclone remote name |
| `RCLONE_PATH` | `pjtracker-backups` | folder on the remote |
| `KEEP_N` | `14` | how many remote tars to keep (`0` = no prune) |
| `KEEP_LOCAL` | `0` | set to `1` to keep the local tar after upload |
| `KEEP_LOCAL_N` | `0` | with `--clean-local`: newest local tars to keep (`0` = delete all) |
| `PJTRACKER_DB_PATH` | `<repo>/pjtracker.db` | override DB (pdfs/images live next to it) |
| `BACKUP_SSH_HOST` | `<hostname>.local` | host printed in the `--local-only` / `--dry-run` scp hint |

Cron example (daily 03:00):

```cron
0 3 * * * cd /path/to/pjtracker && ./scripts/backup.sh >> /tmp/pjtracker-backup.log 2>&1
```

### Restore

Stop the API/UI first. `./scripts/restore.sh` unpacks a `backup.sh` archive into the **current directory** (`pjtracker.db`, `pdfs/`, `images/`). SQLite WAL/SHM files next to the DB are removed so they cannot replay onto the restored snapshot. Folders present in the archive replace the destination folders; missing archive folders are left as-is.

```bash
./scripts/restore.sh --dry-run --latest              # show newest local tar, no write
./scripts/restore.sh pjtracker-20260830-030000.tar.gz
./scripts/restore.sh --latest                        # newest local pjtracker-*.tar.gz
./scripts/restore.sh --from-remote                   # download newest rclone backup, then restore
./scripts/restore.sh --from-remote --dry-run
./scripts/restore.sh --force --latest                # overwrite without prompt
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `PJTRACKER_DB_PATH` | `<cwd>/pjtracker.db` | restore next to this DB (pdfs/images live next to it) |
| `RCLONE_REMOTE` | `gdrive` | rclone remote name (`--from-remote`) |
| `RCLONE_PATH` | `pjtracker-backups` | folder on the remote (`--from-remote`) |

Run from the folder that should receive the data (usually the repo root). `--force` is required when stdin is not a TTY and the destination already has data. Then start again with `./scripts/dev.sh` or `./scripts/prod.sh`.

## Import casa data

Copies bills, people, fixed bills, cars, and car maintenance (JSON + files) from a casa project into `data/casa/`. Rewrites maintenance file paths from `data/maintenance/` to `data/casa/maintenance/`.

By default, JSON files are merged (casa wins on duplicate keys). Use `--overwrite` to replace destination files entirely.

```bash
uv run python scripts/import_casa_data.py /path/to/casa
uv run python scripts/import_casa_data.py /path/to/casa --dry-run
uv run python scripts/import_casa_data.py /path/to/casa --overwrite
```

Pass the casa project root (folder containing `data/people.json` or `data/bills_history.json`). Restart the API after importing if it is already running.

## Deadline checks

Runs registered fiscal deadline checks against the local SQLite DB and optionally emails failures via Gmail SMTP. Current checks: pro-labore withdraw and previous-month DARF receipt.

```bash
uv run pjtracker-check --dry-run          # print results only; do not send email
uv run pjtracker-check                    # run due checks; email on failure
uv run pjtracker-check --force-all        # run all checks, ignoring due windows
uv run pjtracker-check --date 2026-08-15  # simulate "today"
```

Requires a Gmail App Password (Google Account → Security → 2-Step Verification → App passwords). Email is sent only when a check fails (unless `--dry-run`).

| Variable | Default | Purpose |
|----------|---------|---------|
| `PJTRACKER_SMTP_USER` | — | SMTP login (required to send email) |
| `PJTRACKER_SMTP_PASSWORD` | — | Gmail App Password |
| `PJTRACKER_ALERT_TO` | — | Recipient |
| `PJTRACKER_ALERT_FROM` | SMTP user | From address |
| `PJTRACKER_SMTP_HOST` | `smtp.gmail.com` | SMTP host |
| `PJTRACKER_SMTP_PORT` | `587` | SMTP port |
| `PJTRACKER_DB_PATH` | `<repo>/pjtracker.db` | override DB (pdfs/images live next to it) |

Cron example (daily 09:00):

```cron
0 9 * * * cd /path/to/pjtracker && uv run pjtracker-check >> /tmp/pjtracker-check.log 2>&1
```

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
