<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Loader2 } from 'lucide-svelte';

	let { loading = false, disabled = false, onclick }: {
		loading?: boolean;
		disabled?: boolean;
		onclick: () => void;
	} = $props();
</script>

<Button type="button" {onclick} disabled={disabled || loading} variant="outline" class="w-full">
	{#if loading}
		<Loader2 class="h-4 w-4 animate-spin" />
		Processing...
	{:else}
		Process documents
	{/if}
</Button>
