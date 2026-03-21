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
