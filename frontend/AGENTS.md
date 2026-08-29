# pjtracker frontend

SvelteKit app for the FastAPI API. Minimal UI, dark theme (`class="dark"` on `<html>`). No SSR data fetching.

## Run

From `frontend/`: `npm install` then `npm run dev`. API must be up (`uv run uvicorn pjtracker.api.main:app --reload` from repo root). Vite proxies `/api` → `http://127.0.0.1:8000`. Prefer empty `PUBLIC_API_BASE_URL` (same-origin `/api/v1`).

`npm run check` = svelte-check + TypeScript.

## Stack

Svelte **5** (runes), SvelteKit 2, Vite 7, Tailwind **4** (`@theme` in `app.css`), bits-ui (shadcn-svelte-style under `$lib/components/ui/`), lucide-svelte, Unovis, svelte-sonner.

## Conventions

- **Runes only**: `$state`, `$derived`, `$effect`, `$props()`. Layout uses `let { children } = $props()` and `{@render children()}`.
- **Client-side data**: load in `onMount` / `$effect`. Do not add `+page.server.ts`.
- **API**: one function per endpoint in `$lib/api/client.ts`; types in `$lib/api/types.ts`. Pages must not raw-`fetch`. Handle `ApiError` + `formatApiErrorMessage`.
- **Money/dates**: `$lib/utils/format.ts` (`formatBrl`, `formatUsd`, `formatFiscalMes`, `formatDateBr`). Fiscal month is `YYYY-MM`.
- **Reuse**: boletos and DARFs share `BoletoLikePage` with API fns as props. Same pattern if a third boleto-like domain appears.
- **UI kit**: Button, Card, Dialog, Sheet, Table, Tabs, etc. from `$lib/components/ui/`. Toasts via sonner. Confirm destructive actions with `ConfirmDialog`.
- **Upload**: `FileDropZone` → parse-preview → show extracted fields → save. Never skip preview.
- **Theme**: use CSS tokens (`bg-background`, `text-muted-foreground`, `border-border`, …), not ad-hoc palettes.

## Routes

`/` Fluxo (casa + saques + empresa), `/casa`, `/documentos`, `/nfs`, `/boletos`, `/darfs`, `/irpj-csll`, `/extratos`, `/analytics`. Navbar in `Navbar.svelte`.

Deep links filter by fiscal month. Keep that as the organizing axis.
