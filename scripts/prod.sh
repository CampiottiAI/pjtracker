#!/usr/bin/env bash
# Production: build frontend, run uvicorn + Vite preview (no dev reload/HMR).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck source=scripts/_common.sh
source "$ROOT/scripts/_common.sh"
load_maritaca_token
setup_cleanup_trap

PROD_HOST="${PROD_HOST:-0.0.0.0}"
PROD_PORT="${PROD_PORT:-4173}"
API_PORT="${API_PORT:-8000}"

if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "error: frontend dependencies not installed" >&2
  echo "Run: cd frontend && npm install" >&2
  exit 1
fi

echo "Building frontend..."
(cd frontend && npm run build)

echo "Starting backend on 127.0.0.1:$API_PORT (no reload)..."
# #region agent log
_debug_log "H1" "scripts/prod.sh" "backend_spawn" "{\"port\":$API_PORT,\"pid\":\"pending\"}"
# #endregion
uv run uvicorn pjtracker.api.main:app --host 127.0.0.1 --port "$API_PORT" &
BACKEND_PID=$!
# #region agent log
_debug_log "H1" "scripts/prod.sh" "backend_spawned" "{\"port\":$API_PORT,\"pid\":$BACKEND_PID}"
# #endregion

echo "Waiting for backend to be ready..."
wait_for_backend "$API_PORT"

echo "Starting frontend preview on $PROD_HOST:$PROD_PORT..."
# #region agent log
_debug_log "H4" "scripts/prod.sh" "frontend_spawn" "{\"host\":\"$PROD_HOST\",\"port\":$PROD_PORT}"
# #endregion
(cd frontend && npm run preview -- --host "$PROD_HOST" --port "$PROD_PORT") &
FRONTEND_PID=$!

echo ""
echo "Production servers running."
echo "  Open http://localhost:$PROD_PORT"
echo "  LAN:     http://<this-machine-ip>:$PROD_PORT"
echo ""
echo "Optional: PJTRACKER_OCR=0 to skip local OCR (LLM-only parsing)."

wait
