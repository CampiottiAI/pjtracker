<script lang="ts">
	import type { Snippet } from 'svelte';
	import { ChevronDown, Paperclip } from 'lucide-svelte';
	let { ready, count, children }: { ready: boolean; count: number; children: Snippet } = $props();
</script>

<details open={!ready} class="group/files">
	<summary class="mb-3 flex cursor-pointer list-none items-center gap-2 rounded-sm text-sm font-medium [&::-webkit-details-marker]:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
		<Paperclip class="h-4 w-4 text-muted-foreground" />
		<span class="flex-1">Arquivos</span>
		<span class="text-xs font-normal text-muted-foreground">{count} {count === 1 ? 'selecionado' : 'selecionados'}</span>
		<ChevronDown class="h-4 w-4 text-muted-foreground transition-transform group-open/files:rotate-180" />
	</summary>
	<div class="space-y-4">{@render children()}</div>
</details>
