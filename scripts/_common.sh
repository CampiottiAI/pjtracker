#!/usr/bin/env bash
# Shared helpers for dev/prod scripts. Source, do not execute directly.
set -euo pipefail

if [[ -z "${ROOT:-}" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

load_maritaca_token() {
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
}

setup_cleanup_trap() {
  cleanup() {
    if [[ -n "${BACKEND_PID:-}" ]]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
    if [[ -n "${FRONTEND_PID:-}" ]]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
    if [[ -n "${BACKEND_PID:-}" ]]; then wait "$BACKEND_PID" 2>/dev/null || true; fi
    if [[ -n "${FRONTEND_PID:-}" ]]; then wait "$FRONTEND_PID" 2>/dev/null || true; fi
    exit 130
  }
  trap cleanup INT TERM
}

wait_for_backend() {
  local port="${1:-8000}"
  local max_attempts="${BACKEND_READY_ATTEMPTS:-120}"
  local attempt=0
  while (( attempt < max_attempts )); do
    if curl -sf "http://127.0.0.1:${port}/api/v1/ready" >/dev/null 2>&1; then
      return 0
    fi
    attempt=$((attempt + 1))
    sleep 0.5
  done
  echo "error: backend did not become ready on port $port within $((max_attempts / 2))s" >&2
  return 1
}
