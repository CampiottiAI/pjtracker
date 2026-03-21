<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		title,
		description,
		actions
	}: {
		title: string;
		description?: string;
		actions?: Snippet;
	} = $props();
</script>

<div class="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
	<div>
		<h1 class="text-2xl font-semibold tracking-tight">{title}</h1>
		{#if description}
			<p class="text-sm text-muted-foreground mt-1">{description}</p>
		{/if}
	</div>
	{#if actions}
		<div class="flex items-center gap-2 mt-3 sm:mt-0">
			{@render actions()}
		</div>
	{/if}
</div>
