// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

interface ImportMetaEnv {
	/** FastAPI base, e.g. `http://127.0.0.1:8000/api/v1` or empty for same-origin `/api/v1`. */
	readonly PUBLIC_API_BASE_URL?: string;
}

export {};
