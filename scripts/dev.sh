I am#!/usr/bin/env bash
# Run FastAPI + SvelteKit dev servers; Ctrl+C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load Maritaca token from repo-root `.token`; export for child processes.
TOKEN_FILE="$ROOT/.token"
if [[ -z "${MARITACA_API_KEY:-}" ]]; then
  if [[ ! -f "$TOKEN_FILE" ]]; then
    echo "error: missing Maritaca token file at $TOKEN_FILE" >&2
    echo "Set MARITACA_API_KEY or create .token in the repo root." >&2
    exit 1
  fi

  IFS= read -r MARITACA_API_KEY < "$TOKEN_FILE" || true
  MARITACA_API_KEY="${MARITACA_API_KEY//$'\r'/}"
  MARITACA_API_KEY="${MARITACA_API_KEY#"${MARITACA_API_KEY%%[![:space:]]*}"}"
  MARITACA_API_KEY="${MARITACA_API_KEY%"${MARITACA_API_KEY##*[![:space:]]}"}"
  export MARITACA_API_KEY
fi

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
  if [[ -n "${BACKEND_PID:-}" ]]; then wait "$BACKEND_PID" 2>/dev/null || true; fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then wait "$FRONTEND_PID" 2>/dev/null || true; fi
  exit 130
}
trap cleanup INT TERM

uv run uvicorn pjtracker.api.main:app --reload &
BACKEND_PID=$!

(cd frontend && npm run dev) &
FRONTEND_PID=$!

wait
