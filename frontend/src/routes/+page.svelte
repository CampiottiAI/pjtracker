<script lang="ts">
	import { onMount } from 'svelte';
	import { ApiError, getHealth, getReady } from '$lib/api/client';

	let health = $state<string | null>(null);
	let ready = $state<string | null>(null);
	let err = $state<string | null>(null);

	onMount(async () => {
		try {
			const h = await getHealth();
			health = JSON.stringify(h);
			const r = await getReady();
			ready = JSON.stringify(r);
		} catch (e) {
			err = e instanceof ApiError ? `${e.status}: ${e.message}` : String(e);
		}
	});
</script>

<h1>pjtracker frontend</h1>
<p>SvelteKit starter. API integration smoke-check (run FastAPI first):</p>
<ul>
	<li><code>GET /api/v1/health</code>: {health ?? '…'}</li>
	<li><code>GET /api/v1/ready</code>: {ready ?? '…'}</li>
</ul>
{#if err}
	<p role="alert">Error: {err}</p>
{/if}
<p>See <a href="https://svelte.dev/docs/kit">SvelteKit docs</a> and repo <code>docs/api/README.md</code>.</p>
