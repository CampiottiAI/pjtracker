#!/usr/bin/env bash
# Run FastAPI + SvelteKit dev servers; Ctrl+C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=scripts/_common.sh
source "$ROOT/scripts/_common.sh"
load_maritaca_token
setup_cleanup_trap

DEV_HOST="${DEV_HOST:-0.0.0.0}"
echo "Dev servers binding to $DEV_HOST (use this machine's LAN IP from other devices)"

uv run uvicorn pjtracker.api.main:app --reload --host "$DEV_HOST" &
BACKEND_PID=$!

(cd frontend && npm run dev -- --host "$DEV_HOST") &
FRONTEND_PID=$!

wait
