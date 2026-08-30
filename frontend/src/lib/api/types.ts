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
	/** Extra PDF (IRPJ/CSLL only), stored without parsing. */
	attachment_pdf_path?: string | null;
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

/** Withdrawals. */
export type WithdrawEntry = {
	id: number;
	fiscal_mes: string;
	amount_brl: number;
	withdraw_date: string | null;
	notes: string | null;
	created_at: string;
};

export type WithdrawSummary = {
	target_brl: number;
	total_brl: number;
	remaining_brl: number;
	over_target_brl: number;
	target_reached: boolean;
	previous_month_income_brl: number;
};

export type WithdrawListResponse = {
	items: WithdrawEntry[];
	summary: WithdrawSummary;
};

export type CreateWithdrawPayload = {
	fiscal_mes: string;
	amount_brl: number;
	withdraw_date?: string | null;
	notes?: string | null;
};

export type PatchWithdrawPayload = {
	fiscal_mes?: string | null;
	amount_brl?: number;
	withdraw_date?: string | null;
	notes?: string | null;
};

// ---------------------------------------------------------------------------
// Casa (household)
// ---------------------------------------------------------------------------

export type CasaPerson = {
	id: string;
	name: string;
};

export type CasaFixedBill = {
	name: string;
	value: number;
	paid_by: string;
};

export type CasaExpenseItem = {
	description: string;
	amount: number;
	paid_by: string;
	split: boolean;
};

export type CasaCreditCard = {
	name: string;
	value: number;
};

export type CasaSplitPayload = {
	person_ids: string[];
	person_names: string[];
	amounts: number[];
	other_expenses: CasaExpenseItem[];
	fixed_bills: CasaFixedBill[];
	nubank: number;
	cards: CasaCreditCard[];
	pcts: number[];
	total: number;
	nubank_per_person: number[];
	reimbursements: number[];
	cc_reserved_amount: number;
	cc_reserved_person_id: string | null;
	primary_person_id: string;
	primary_share_brl: number;
	primary_pay_now_brl: number;
};

export type CasaWorkspaceResponse = {
	fiscal_mes: string;
	saved: boolean;
	people: CasaPerson[];
	fixed_bills: CasaFixedBill[];
	other_expenses: CasaExpenseItem[];
	nubank: number;
	cards: CasaCreditCard[];
	person_ids: string[];
	pcts: number[];
	cc_reserved_amount: number;
	cc_reserved_person_id: string | null;
	split: CasaSplitPayload;
};

export type CasaSummary = {
	saved: boolean;
	estimated: boolean;
	fiscal_mes: string;
	total_brl: number;
	household_total_brl: number;
	primary_share_brl: number;
	primary_pay_now_brl: number;
	person_ids: string[];
	person_names: string[];
	nubank_per_person: number[];
	reimbursements: number[];
	pcts: number[];
	nubank: number;
	cards: CasaCreditCard[];
};

export type CasaComputeSplitPayload = {
	fiscal_mes: string;
	person_ids: string[];
	pcts: number[];
	nubank: number;
	cards: CasaCreditCard[];
	fixed_bills: CasaFixedBill[];
	other_expenses: CasaExpenseItem[];
	cc_reserved_amount?: number;
	cc_reserved_person_id?: string | null;
};

// ---------------------------------------------------------------------------
// Fluxo
// ---------------------------------------------------------------------------

export type FluxoCoverage = {
	covers_household: boolean;
	surplus_brl: number;
	shortfall_brl: number;
	saques_brl: number;
	primary_share_brl: number;
	household_total_brl: number;
};

export type FluxoCompany = {
	saldo_final_brl: number | null;
	has_extrato: boolean;
	restante_brl: number;
	restante_estimated: boolean;
	taxes_brl: number;
	nf_income_brl: number;
};

export type FluxoResponse = {
	fiscal_mes: string;
	previous_fiscal_mes: string;
	withdraw_summary: WithdrawSummary;
	casa: CasaSummary;
	coverage: FluxoCoverage;
	company: FluxoCompany;
	completeness: CompletenessResponse;
	completeness_missing_count: number;
};

export type FluxoSeriesPoint = {
	fiscal_mes: string;
	saques_brl: number;
	primary_share_brl: number;
	household_total_brl: number;
	previous_month_income_brl: number;
	casa_saved: boolean;
};

export type FluxoSeriesResponse = {
	points: FluxoSeriesPoint[];
};
