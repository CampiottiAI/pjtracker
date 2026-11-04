<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import { Loader2, ArrowRight, Check } from 'lucide-svelte';

	let { ready, processing, saving, canProcess, canSave, onprocess, onsave, oncancel }: {
		ready: boolean;
		processing: boolean;
		saving: boolean;
		canProcess: boolean;
		canSave: boolean;
		onprocess: () => void;
		onsave: () => void;
		oncancel: () => void;
	} = $props();
</script>

<Sheet.SheetFooter class="flex-col items-stretch sm:flex-col sm:items-stretch">
	<p class="mb-1 text-xs text-muted-foreground">
		{ready ? 'Confira os dados antes de salvar.' : 'Selecione os arquivos. Você poderá revisar antes de salvar.'}
	</p>
	<div class="flex items-center justify-between gap-3">
		<Button type="button" variant="ghost" onclick={oncancel} disabled={saving}>Cancelar</Button>
		{#if ready}
			<Button type="button" onclick={onsave} disabled={saving || processing || !canSave}>
				{#if saving}<Loader2 class="h-4 w-4 animate-spin" />{:else}<Check class="h-4 w-4" />{/if}
				{saving ? 'Salvando…' : 'Salvar'}
			</Button>
		{:else}
			<Button type="button" onclick={onprocess} disabled={processing || saving || !canProcess}>
				{#if processing}<Loader2 class="h-4 w-4 animate-spin" />{/if}
				{processing ? 'Processando…' : 'Processar'}
				{#if !processing}<ArrowRight class="h-4 w-4" />{/if}
			</Button>
		{/if}
	</div>
</Sheet.SheetFooter>
