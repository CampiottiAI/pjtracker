<script lang="ts">
	import { Input } from '$lib/components/ui/input/index.js';

	let {
		value = $bindable(''),
		months = [],
		placeholder = 'YYYY-MM'
	}: {
		value?: string;
		months?: string[];
		placeholder?: string;
	} = $props();
</script>

{#if months.length > 0}
	<select
		class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
		bind:value
	>
		<option value="">All months</option>
		{#each months as m}
			<option value={m}>{m}</option>
		{/each}
	</select>
{:else}
	<Input type="text" {placeholder} bind:value pattern="\d{4}-\d{2}" />
{/if}
