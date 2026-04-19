/**
 * Shared types for pjtracker FastAPI (`/api/v1`).
 * See repo `docs/api/README.md` for contract details.
 */

/** `GET /health` */
export type HealthResponse = {
	status: string;
};

/** `GET /ready` */
export type ReadyResponse = {
	ready: boolean;
	database: boolean;
	llm_key_configured: boolean;
	token_file_exists: boolean;
};

/** Nested shape used by some `409 Conflict` responses (e.g. duplicate NF). */
export type ApiConflictDetail = {
	detail?: string;
	code?: string;
	existing_id?: number;
	[key: string]: unknown;
};

/** Typical FastAPI error JSON; `detail` is not always a string. */
export type FastApiErrorBody = {
	detail?: string | ApiConflictDetail | ApiConflictDetail[] | unknown;
	[key: string]: unknown;
};

// ---------------------------------------------------------------------------
// Domain types
// ---------------------------------------------------------------------------

/** NF entry as returned by list/get/create endpoints. */
export type NfEntry = {
	id: number;
	company: string | null;
	usd: number;
	rate: number;
	spread: number;
	brl_no_spread: number;
	brl_with_spread: number;
	nf_date: string | null;
	verification_code: string | null;
	payment_via: string | null;
	pdf_path: string | null;
	fiscal_mes: string | null;
	created_at: string;
};

/** NF parse-preview response. */
export type NfPreview = {
	company: string | null;
	usd: number | null;
	rate: number | null;
	spread: number | null;
	spread_was_default: boolean;
	nf_date: string | null;
	verification_code: string | null;
	payment_via: string | null;
	source: string;
	brl: { brl_no_spread: number; brl_with_spread: number } | null;
};

/** NF image row. */
export type NfImage = {
	id: number;
	nf_id: number;
	image_path: string;
	created_at: string;
};

/** Boleto / DARF entry (same shape). */
export type BoletoEntry = {
	id: number;
	pdf_path: string;
	receipt_path: string | null;
	value: number | null;
	emission_date: string | null;
	deadline_date: string | null;
	receipt_date: string | null;
	codigo_barras: string | null;
	codigo_barras_digits: string | null;
	receipt_value: number | null;
	receipt_codigo_barras: string | null;
	receipt_codigo_barras_digits: string | null;
	receipt_match_status: 'match' | 'mismatch' | null;
	content_hash: string | null;
	fiscal_mes: string | null;
	created_at: string;
	updated_at: string | null;
};

export type DarfEntry = BoletoEntry;
export type IrpjCsllEntry = BoletoEntry;

export type BoletoLikeFieldsPatch = {
	value: number | null;
	emission_date: string | null;
	deadline_date: string | null;
	codigo_barras: string | null;
	codigo_barras_digits: string | null;
	receipt_date: string | null;
	receipt_value: number | null;
	receipt_codigo_barras: string | null;
	receipt_codigo_barras_digits: string | null;
	fiscal_mes: string | null;
};

/** Boleto/DARF parse-preview. */
export type BoletoPreview = {
	value: number | null;
	emission_date: string | null;
	deadline_date: string | null;
	codigo_barras_raw: string | null;
	codigo_barras_digits: string | null;
	source: string;
};

export type DarfPreview = BoletoPreview;
export type IrpjCsllPreview = BoletoPreview;

/** Receipt parse-preview. */
export type ReceiptPreview = {
	value: number | null;
	payment_datetime: string | null;
	codigo_barras_raw: string | null;
	codigo_barras_digits: string | null;
	source: string;
};

/** Extrato entry. */
export type ExtratoEntry = {
	id: number;
	extrato_pdf_path: string;
	caixinha_pdf_path: string | null;
	higlobe_pdf_path: string | null;
	period_start: string | null;
	period_end: string | null;
	saldo_inicial: number | null;
	rendimento: number | null;
	total_entradas: number | null;
	total_saidas: number | null;
	saldo_final: number | null;
	caixinha_saldo_final: number | null;
	extrato_entries_json: string | null;
	caixinha_entries_json: string | null;
	higlobe_entries_json: string | null;
	content_hash: string | null;
	fiscal_mes: string | null;
	created_at: string;
	updated_at: string | null;
};

/** Extrato parse-preview sub-shapes. */
export type ExtratoParsedPreview = {
	period_start: string | null;
	period_end: string | null;
	saldo_inicial: number | null;
	rendimento: number | null;
	total_entradas: number | null;
	total_saidas: number | null;
	saldo_final: number | null;
	entries: Record<string, unknown>[];
	source: string;
};

export type CaixinhaParsedPreview = {
	saldo_final: number | null;
	period_start: string | null;
	period_end: string | null;
	entries: Record<string, unknown>[];
	source: string;
};

export type HiglobeParsedPreview = {
	period_start: string | null;
	period_end: string | null;
	entries: Record<string, unknown>[];
	source: string;
};

export type ExtratoPreview = {
	extrato: ExtratoParsedPreview;
	caixinha: CaixinhaParsedPreview | null;
	higlobe: HiglobeParsedPreview | null;
};

/** Fiscal months. */
export type FiscalMonthsResponse = {
	months: string[];
};

export type CreateFiscalMonthResponse = {
	fiscal_mes: string;
	created: boolean;
};

/** Fiscal month completeness. */
export type CompletenessResponse = {
	fiscal_mes: string;
	nfs_count: number;
	nfs_ok: boolean;
	boletos_with_receipt_count: number;
	boletos_ok: boolean;
	darfs_with_receipt_count: number;
	darfs_ok: boolean;
	irpj_csll_with_receipt_count: number;
	irpj_csll_required: boolean;
	irpj_csll_ok: boolean;
	extratos_caixinha_count: number;
	extratos_ok: boolean;
	extratos_higlobe_count: number;
	higlobe_ok: boolean;
	month_complete: boolean;
};

/** Analytics NF series point. */
export type NfSeriesPoint = {
	date: string;
	usd: number;
	brl_no_spread: number;
	brl_with_spread: number;
	rate: number;
	spread: number;
	effective_rate: number;
};

export type NfSeriesResponse = {
	points: NfSeriesPoint[];
};
