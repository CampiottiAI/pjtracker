import type {
	FastApiErrorBody,
	HealthResponse,
	ReadyResponse,
	NfEntry,
	NfPreview,
	NfImage,
	BoletoEntry,
	BoletoLikeFieldsPatch,
	BoletoPreview,
	DarfEntry,
	DarfPreview,
	IrpjCsllEntry,
	IrpjCsllPreview,
	ReceiptPreview,
	ExtratoEntry,
	ExtratoPreview,
	FiscalMonthsResponse,
	CreateFiscalMonthResponse,
	CompletenessResponse,
	NfSeriesResponse
} from './types';

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

// ---------------------------------------------------------------------------
// NFs
// ---------------------------------------------------------------------------

export async function nfParsePreview(file: File): Promise<NfPreview> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<NfPreview>('/nfs/parse-preview', form);
}

export async function createNf(file: File, fiscalMes: string, images?: File[]): Promise<NfEntry> {
	const form = new FormData();
	form.append('file', file);
	form.append('fiscal_mes', fiscalMes);
	if (images) images.forEach((img) => form.append('images', img));
	return apiForm<NfEntry>('/nfs', form);
}

export async function listNfs(params?: {
	fiscal_mes?: string;
	date_from?: string;
	date_to?: string;
}): Promise<NfEntry[]> {
	const qs = new URLSearchParams();
	if (params?.fiscal_mes) qs.set('fiscal_mes', params.fiscal_mes);
	if (params?.date_from) qs.set('date_from', params.date_from);
	if (params?.date_to) qs.set('date_to', params.date_to);
	const q = qs.toString();
	return apiJson<NfEntry[]>(`/nfs${q ? `?${q}` : ''}`);
}

export async function getNf(id: number): Promise<NfEntry> {
	return apiJson<NfEntry>(`/nfs/${id}`);
}

export async function patchNfFiscalMes(id: number, fiscalMes: string | null): Promise<NfEntry> {
	return apiJson<NfEntry>(`/nfs/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ fiscal_mes: fiscalMes })
	});
}

export async function deleteNf(id: number): Promise<void> {
	await apiJson(`/nfs/${id}`, { method: 'DELETE' });
}

export async function getNfImages(nfId: number): Promise<NfImage[]> {
	return apiJson<NfImage[]>(`/nfs/${nfId}/images`);
}

export async function updateNfPdf(id: number, file: File): Promise<NfEntry> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<NfEntry>(`/nfs/${id}/pdf`, form, 'PUT');
}

export async function addNfImages(nfId: number, images: File[]): Promise<NfImage[]> {
	const form = new FormData();
	images.forEach((img) => form.append('images', img));
	return apiForm<NfImage[]>(`/nfs/${nfId}/images`, form);
}

export async function deleteNfImage(nfId: number, imageId: number): Promise<void> {
	await apiJson(`/nfs/${nfId}/images/${imageId}`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Boletos
// ---------------------------------------------------------------------------

export async function boletoParsePreview(file: File): Promise<BoletoPreview> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<BoletoPreview>('/boletos/parse-preview', form);
}

export async function receiptParsePreview(file: File): Promise<ReceiptPreview> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<ReceiptPreview>('/receipts/parse-preview', form);
}

export async function createBoleto(
	file: File,
	fiscalMes: string,
	receipt?: File,
	receiptDate?: string,
	receiptTime?: string
): Promise<BoletoEntry> {
	const form = new FormData();
	form.append('file', file);
	form.append('fiscal_mes', fiscalMes);
	if (receipt) form.append('receipt', receipt);
	if (receiptDate) form.append('receipt_date', receiptDate);
	if (receiptTime) form.append('receipt_time', receiptTime);
	return apiForm<BoletoEntry>('/boletos', form);
}

export async function listBoletos(fiscalMes?: string): Promise<BoletoEntry[]> {
	const q = fiscalMes ? `?fiscal_mes=${fiscalMes}` : '';
	return apiJson<BoletoEntry[]>(`/boletos${q}`);
}

export async function getBoleto(id: number): Promise<BoletoEntry> {
	return apiJson<BoletoEntry>(`/boletos/${id}`);
}

export async function patchBoletoFiscalMes(
	id: number,
	fiscalMes: string | null
): Promise<BoletoEntry> {
	return apiJson<BoletoEntry>(`/boletos/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ fiscal_mes: fiscalMes })
	});
}

export async function patchBoletoFields(
	id: number,
	payload: BoletoLikeFieldsPatch
): Promise<BoletoEntry> {
	return apiJson<BoletoEntry>(`/boletos/${id}/fields`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
}

export async function updateBoletoPdf(id: number, file: File): Promise<BoletoEntry> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<BoletoEntry>(`/boletos/${id}/pdf`, form, 'PUT');
}

export async function updateBoletoReceipt(
	id: number,
	receipt: File,
	receiptDate?: string,
	receiptTime?: string
): Promise<BoletoEntry> {
	const form = new FormData();
	form.append('receipt', receipt);
	if (receiptDate) form.append('receipt_date', receiptDate);
	if (receiptTime) form.append('receipt_time', receiptTime);
	return apiForm<BoletoEntry>(`/boletos/${id}/receipt`, form, 'PUT');
}

export async function reprocessBoleto(id: number): Promise<BoletoEntry> {
	return apiJson<BoletoEntry>(`/boletos/${id}/reprocess`, { method: 'POST' });
}

export async function deleteBoleto(id: number): Promise<void> {
	await apiJson(`/boletos/${id}`, { method: 'DELETE' });
}

export async function getBoletoBarcodeDiff(id: number): Promise<string> {
	const { blob } = await downloadBlob(`/boletos/${id}/barcode-diff`);
	return blob.text();
}

// ---------------------------------------------------------------------------
// DARFs
// ---------------------------------------------------------------------------

export async function darfParsePreview(file: File): Promise<DarfPreview> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<DarfPreview>('/darfs/parse-preview', form);
}

export async function createDarf(
	file: File,
	fiscalMes: string,
	receipt?: File,
	receiptDate?: string,
	receiptTime?: string
): Promise<DarfEntry> {
	const form = new FormData();
	form.append('file', file);
	form.append('fiscal_mes', fiscalMes);
	if (receipt) form.append('receipt', receipt);
	if (receiptDate) form.append('receipt_date', receiptDate);
	if (receiptTime) form.append('receipt_time', receiptTime);
	return apiForm<DarfEntry>('/darfs', form);
}

export async function listDarfs(fiscalMes?: string): Promise<DarfEntry[]> {
	const q = fiscalMes ? `?fiscal_mes=${fiscalMes}` : '';
	return apiJson<DarfEntry[]>(`/darfs${q}`);
}

export async function getDarf(id: number): Promise<DarfEntry> {
	return apiJson<DarfEntry>(`/darfs/${id}`);
}

export async function patchDarfFiscalMes(
	id: number,
	fiscalMes: string | null
): Promise<DarfEntry> {
	return apiJson<DarfEntry>(`/darfs/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ fiscal_mes: fiscalMes })
	});
}

export async function patchDarfFields(
	id: number,
	payload: BoletoLikeFieldsPatch
): Promise<DarfEntry> {
	return apiJson<DarfEntry>(`/darfs/${id}/fields`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
}

export async function updateDarfPdf(id: number, file: File): Promise<DarfEntry> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<DarfEntry>(`/darfs/${id}/pdf`, form, 'PUT');
}

export async function updateDarfReceipt(
	id: number,
	receipt: File,
	receiptDate?: string,
	receiptTime?: string
): Promise<DarfEntry> {
	const form = new FormData();
	form.append('receipt', receipt);
	if (receiptDate) form.append('receipt_date', receiptDate);
	if (receiptTime) form.append('receipt_time', receiptTime);
	return apiForm<DarfEntry>(`/darfs/${id}/receipt`, form, 'PUT');
}

export async function deleteDarf(id: number): Promise<void> {
	await apiJson(`/darfs/${id}`, { method: 'DELETE' });
}

export async function getDarfBarcodeDiff(id: number): Promise<string> {
	const { blob } = await downloadBlob(`/darfs/${id}/barcode-diff`);
	return blob.text();
}

// ---------------------------------------------------------------------------
// IRPJ/CSLL
// ---------------------------------------------------------------------------

export async function irpjCsllParsePreview(file: File): Promise<IrpjCsllPreview> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<IrpjCsllPreview>('/irpj-csll/parse-preview', form);
}

export async function createIrpjCsll(
	file: File,
	fiscalMes: string,
	receipt?: File,
	receiptDate?: string,
	receiptTime?: string
): Promise<IrpjCsllEntry> {
	const form = new FormData();
	form.append('file', file);
	form.append('fiscal_mes', fiscalMes);
	if (receipt) form.append('receipt', receipt);
	if (receiptDate) form.append('receipt_date', receiptDate);
	if (receiptTime) form.append('receipt_time', receiptTime);
	return apiForm<IrpjCsllEntry>('/irpj-csll', form);
}

export async function listIrpjCsll(fiscalMes?: string): Promise<IrpjCsllEntry[]> {
	const q = fiscalMes ? `?fiscal_mes=${fiscalMes}` : '';
	return apiJson<IrpjCsllEntry[]>(`/irpj-csll${q}`);
}

export async function getIrpjCsll(id: number): Promise<IrpjCsllEntry> {
	return apiJson<IrpjCsllEntry>(`/irpj-csll/${id}`);
}

export async function patchIrpjCsllFiscalMes(
	id: number,
	fiscalMes: string | null
): Promise<IrpjCsllEntry> {
	return apiJson<IrpjCsllEntry>(`/irpj-csll/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ fiscal_mes: fiscalMes })
	});
}

export async function patchIrpjCsllFields(
	id: number,
	payload: BoletoLikeFieldsPatch
): Promise<IrpjCsllEntry> {
	return apiJson<IrpjCsllEntry>(`/irpj-csll/${id}/fields`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(payload)
	});
}

export async function updateIrpjCsllPdf(id: number, file: File): Promise<IrpjCsllEntry> {
	const form = new FormData();
	form.append('file', file);
	return apiForm<IrpjCsllEntry>(`/irpj-csll/${id}/pdf`, form, 'PUT');
}

export async function updateIrpjCsllReceipt(
	id: number,
	receipt: File,
	receiptDate?: string,
	receiptTime?: string
): Promise<IrpjCsllEntry> {
	const form = new FormData();
	form.append('file', receipt);
	if (receiptDate) form.append('receipt_date', receiptDate);
	if (receiptTime) form.append('receipt_time', receiptTime);
	return apiForm<IrpjCsllEntry>(`/irpj-csll/${id}/receipt`, form, 'PUT');
}

export async function deleteIrpjCsll(id: number): Promise<void> {
	await apiJson(`/irpj-csll/${id}`, { method: 'DELETE' });
}

export async function getIrpjCsllBarcodeDiff(id: number): Promise<string> {
	const { blob } = await downloadBlob(`/irpj-csll/${id}/barcode-diff`);
	return blob.text();
}

// ---------------------------------------------------------------------------
// Extratos
// ---------------------------------------------------------------------------

export async function extratoParsePreview(
	extrato: File,
	caixinha?: File,
	higlobe?: File
): Promise<ExtratoPreview> {
	const form = new FormData();
	form.append('extrato', extrato);
	if (caixinha) form.append('caixinha', caixinha);
	if (higlobe) form.append('higlobe', higlobe);
	return apiForm<ExtratoPreview>('/extratos/parse-preview', form);
}

export async function createExtrato(
	extrato: File,
	fiscalMes: string,
	caixinha?: File,
	higlobe?: File
): Promise<ExtratoEntry> {
	const form = new FormData();
	form.append('extrato', extrato);
	form.append('fiscal_mes', fiscalMes);
	if (caixinha) form.append('caixinha', caixinha);
	if (higlobe) form.append('higlobe', higlobe);
	return apiForm<ExtratoEntry>('/extratos', form);
}

export async function listExtratos(fiscalMes?: string): Promise<ExtratoEntry[]> {
	const q = fiscalMes ? `?fiscal_mes=${fiscalMes}` : '';
	return apiJson<ExtratoEntry[]>(`/extratos${q}`);
}

export async function getExtrato(id: number): Promise<ExtratoEntry> {
	return apiJson<ExtratoEntry>(`/extratos/${id}`);
}

export async function patchExtratoFiscalMes(
	id: number,
	fiscalMes: string | null
): Promise<ExtratoEntry> {
	return apiJson<ExtratoEntry>(`/extratos/${id}`, {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ fiscal_mes: fiscalMes })
	});
}

export async function deleteExtrato(id: number): Promise<void> {
	await apiJson(`/extratos/${id}`, { method: 'DELETE' });
}

export async function updateExtratoPdf(id: number, file: File): Promise<ExtratoEntry> {
	const form = new FormData();
	form.append('extrato', file);
	return apiForm<ExtratoEntry>(`/extratos/${id}/extrato-pdf`, form, 'PUT');
}

export async function updateCaixinhaPdf(id: number, file: File): Promise<ExtratoEntry> {
	const form = new FormData();
	form.append('caixinha', file);
	return apiForm<ExtratoEntry>(`/extratos/${id}/caixinha`, form, 'PUT');
}

export async function deleteCaixinha(id: number): Promise<void> {
	await apiJson(`/extratos/${id}/caixinha`, { method: 'DELETE' });
}

export async function updateHiglobePdf(id: number, file: File): Promise<ExtratoEntry> {
	const form = new FormData();
	form.append('higlobe', file);
	return apiForm<ExtratoEntry>(`/extratos/${id}/higlobe`, form, 'PUT');
}

export async function deleteHiglobe(id: number): Promise<void> {
	await apiJson(`/extratos/${id}/higlobe`, { method: 'DELETE' });
}

// ---------------------------------------------------------------------------
// Fiscal months
// ---------------------------------------------------------------------------

export async function listFiscalMonths(): Promise<FiscalMonthsResponse> {
	return apiJson<FiscalMonthsResponse>('/fiscal-months');
}

export async function createFiscalMonth(fiscalMes: string): Promise<CreateFiscalMonthResponse> {
	return apiJson<CreateFiscalMonthResponse>('/fiscal-months', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ fiscal_mes: fiscalMes })
	});
}

export async function getCompleteness(fiscalMes: string): Promise<CompletenessResponse> {
	return apiJson<CompletenessResponse>(`/fiscal-months/${fiscalMes}/completeness`);
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

export async function getNfSeries(dateFrom: string, dateTo: string): Promise<NfSeriesResponse> {
	return apiJson<NfSeriesResponse>(
		`/analytics/nf-series?date_from=${dateFrom}&date_to=${dateTo}`
	);
}
