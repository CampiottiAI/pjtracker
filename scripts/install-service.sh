#!/usr/bin/env bash
# Run as your normal user on the Pi; sudo is used only for systemd setup.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "$(uname -s)" != Linux ]]; then
  echo "error: this installer requires Linux with systemd" >&2
  exit 1
fi
if [[ "$EUID" == 0 ]]; then
  echo "error: run this script as your normal user, without sudo" >&2
  exit 1
fi
for command in systemctl sudo uv node npm curl; do
  if ! command -v "$command" >/dev/null; then
    echo "error: install $command first and ensure it is on PATH" >&2
    exit 1
  fi
done

SERVICE_USER="$(id -un)"
SERVICE_PATH="$(dirname "$(command -v uv)"):$(dirname "$(command -v node)"):$(dirname "$(command -v npm)"):/usr/local/bin:/usr/bin:/bin"
# Keep generated unit values literal, including systemd specifiers and shell variables.
for value in "$ROOT" "$SERVICE_USER" "$SERVICE_PATH"; do
  if [[ ! "$value" =~ ^[a-zA-Z0-9_./:@+-]+$ ]]; then
    echo "error: username, repo and executable paths must contain only letters, numbers, _ . / : @ + -" >&2
    exit 1
  fi
done
if [[ ! -s "$ROOT/.token" && ! -f /etc/pjtracker.env ]]; then
  echo "error: put the Maritaca key in $ROOT/.token before installing" >&2
  echo "Alternatively, configure MARITACA_API_KEY in /etc/pjtracker.env." >&2
  exit 1
fi

cd "$ROOT"
echo "Installing dependencies and building the frontend as $SERVICE_USER..."
uv sync --frozen
(cd frontend && npm ci && npm run build)

UNIT_FILE="$(mktemp)"
trap 'rm -f "$UNIT_FILE"' EXIT
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=PJTracker API and frontend
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$ROOT
Environment="PATH=$SERVICE_PATH"
Environment="PYTHONUNBUFFERED=1"
Environment="PROD_HOST=0.0.0.0"
Environment="PROD_PORT=4173"
EnvironmentFile=-/etc/pjtracker.env
ExecStart=/bin/bash $ROOT/scripts/prod.sh
Restart=always
RestartSec=5
KillMode=control-group
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF

sudo install -m 644 "$UNIT_FILE" /etc/systemd/system/pjtracker.service
sudo systemctl daemon-reload
sudo systemctl enable pjtracker.service
sudo systemctl restart pjtracker.service
sudo systemctl status pjtracker.service --no-pager
echo "Open http://<pi-ip>:4173 (or your configured PROD_PORT)."
echo "Logs: sudo journalctl -u pjtracker -f"
