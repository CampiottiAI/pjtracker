<script lang="ts">
	import { cn } from '$lib/utils.js';
	import { Check } from 'lucide-svelte';
	let { ready = false }: { ready?: boolean } = $props();
</script>

<ol aria-label="Etapas do envio" class="mt-3 flex items-center gap-3 text-xs">
	{#each ['Arquivos', 'Revisar e salvar'] as label, index}
		<li aria-current={index === (ready ? 1 : 0) ? 'step' : undefined} class={cn('flex items-center gap-2', index === (ready ? 1 : 0) ? 'text-primary' : 'text-muted-foreground')}>
			<span class={cn('flex h-5 w-5 items-center justify-center rounded-full border text-[10px]', index === (ready ? 1 : 0) ? 'border-primary/40 bg-primary/10' : 'border-border')}>
				{#if index === 0 && ready}<Check class="h-3 w-3" />{:else}{index + 1}{/if}
			</span>
			{label}
		</li>
		{#if index === 0}<li aria-hidden="true" class="h-px w-6 bg-border"></li>{/if}
	{/each}
</ol>
