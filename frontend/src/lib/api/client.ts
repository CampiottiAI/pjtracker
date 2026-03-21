import type { FastApiErrorBody, HealthResponse, ReadyResponse } from './types';

/**
 * Base URL for API calls, without trailing slash.
 * - Set `PUBLIC_API_BASE_URL` in `.env` (e.g. `http://127.0.0.1:8000/api/v1` for direct calls).
 * - If unset, defaults to `/api/v1` (same-origin; use Vite dev proxy — see `vite.config.ts`).
 */
export function getApiBaseUrl(): string {
	const raw = import.meta.env.PUBLIC_API_BASE_URL;
	const base = typeof raw === 'string' ? raw.trim() : '';
	if (base) return base.replace(/\/$/, '');
	return '/api/v1';
}

function joinUrl(path: string): string {
	const base = getApiBaseUrl();
	const p = path.startsWith('/') ? path : `/${path}`;
	return `${base}${p}`;
}

export class ApiError extends Error {
	readonly status: number;
	readonly body: unknown;

	constructor(status: number, body: unknown, message?: string) {
		super(message ?? `HTTP ${status}`);
		this.name = 'ApiError';
		this.status = status;
		this.body = body;
	}
}

/** Human-readable message from FastAPI JSON or fallback. */
export function formatApiErrorMessage(body: unknown): string {
	if (body === null || body === undefined) return 'Request failed';
	if (typeof body === 'string') return body;
	if (typeof body === 'object' && body !== null && 'detail' in body) {
		const d = (body as FastApiErrorBody).detail;
		if (typeof d === 'string') return d;
		if (d && typeof d === 'object' && !Array.isArray(d) && 'detail' in d) {
			const inner = (d as { detail?: unknown }).detail;
			if (typeof inner === 'string') return inner;
		}
		if (Array.isArray(d) && d.length > 0 && typeof d[0] === 'object' && d[0] !== null) {
			const first = d[0] as { msg?: string };
			if (typeof first.msg === 'string') return first.msg;
		}
	}
	try {
		return JSON.stringify(body);
	} catch {
		return 'Request failed';
	}
}

async function parseJsonBody(response: Response): Promise<unknown> {
	const text = await response.text();
	if (!text) return null;
	try {
		return JSON.parse(text) as unknown;
	} catch {
		return text;
	}
}

/** JSON request (GET/POST with JSON body, PATCH, etc.). */
export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
	const url = joinUrl(path);
	const response = await fetch(url, {
		...init,
		headers: {
			Accept: 'application/json',
			...(init?.headers as Record<string, string> | undefined)
		}
	});
	const body = await parseJsonBody(response);
	if (!response.ok) {
		throw new ApiError(response.status, body, formatApiErrorMessage(body));
	}
	return body as T;
}

/** Multipart upload (parse-preview, create with files). */
export async function apiForm<T>(path: string, form: FormData, method = 'POST'): Promise<T> {
	const url = joinUrl(path);
	const response = await fetch(url, { method, body: form });
	const parsed = await parseJsonBody(response);
	if (!response.ok) {
		throw new ApiError(response.status, parsed, formatApiErrorMessage(parsed));
	}
	return parsed as T;
}

/** Binary download (PDF, images, plain text). Returns blob + optional filename from Content-Disposition. */
export async function downloadBlob(
	path: string,
	init?: RequestInit
): Promise<{ blob: Blob; filename?: string }> {
	const url = joinUrl(path);
	const response = await fetch(url, init);
	if (!response.ok) {
		const parsed = await parseJsonBody(response);
		throw new ApiError(response.status, parsed, formatApiErrorMessage(parsed));
	}
	const blob = await response.blob();
	const cd = response.headers.get('content-disposition');
	let filename: string | undefined;
	if (cd) {
		const m = /filename\*?=(?:UTF-8'')?["']?([^";\n]+)/i.exec(cd);
		if (m?.[1]) filename = decodeURIComponent(m[1].replace(/["']/g, ''));
	}
	return { blob, filename };
}

/** Trigger browser download of a blob (client-only). */
export function triggerDownload(blob: Blob, filename?: string): void {
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	if (filename) a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

export async function getHealth(): Promise<HealthResponse> {
	return apiJson<HealthResponse>('/health');
}

export async function getReady(): Promise<ReadyResponse> {
	return apiJson<ReadyResponse>('/ready');
}
