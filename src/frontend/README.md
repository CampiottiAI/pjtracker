# pjtracker frontend (SvelteKit)

Standalone SvelteKit app for the pjtracker FastAPI backend (`src/api/`). UI is intentionally minimal; this folder bootstraps the toolchain and API helpers.

## Prerequisites

- **Node.js** (LTS recommended) and **npm**
- **Python** backend: from the repo root, `uv sync` then run the API (see root [README.md](../../README.md))

## Setup

```bash
cd src/frontend
npm install
cp .env.example .env   # optional; default empty PUBLIC_API_BASE_URL uses `/api/v1` + dev proxy
```

## Environment

| Variable | Purpose |
|----------|---------|
| `PUBLIC_API_BASE_URL` | API base **without** trailing slash. Empty = same-origin `/api/v1` (works with Vite dev proxy). Set to `http://127.0.0.1:8000/api/v1` for direct browser calls (requires CORS on the API). |

## Local development (two terminals)

**Terminal 1 — FastAPI** (repo root):

```bash
uv run uvicorn src.api.main:app --reload
```

API: `http://127.0.0.1:8000/api/v1` · Swagger: `http://127.0.0.1:8000/docs`

**Terminal 2 — SvelteKit** (`src/frontend`):

```bash
npm run dev
```

Vite proxies `/api/*` to `http://127.0.0.1:8000` (see `vite.config.ts`), so the browser can call `/api/v1/...` without CORS issues during dev.

## API helpers

- [`src/lib/api/client.ts`](src/lib/api/client.ts) — `apiJson`, `apiForm`, `downloadBlob`, `getHealth`, `getReady`
- [`src/lib/api/types.ts`](src/lib/api/types.ts) — shared response/error shapes

Full contract: [docs/api/README.md](../../docs/api/README.md).

## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Dev server |
| `npm run build` | Production build |
| `npm run preview` | Preview production build |
| `npm run check` | `svelte-check` + TypeScript |

## Recreate this scaffold

```bash
npx sv@0.12.8 create --template minimal --types ts --no-install src/frontend
```
