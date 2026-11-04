<script lang="ts">
	import { getCompleteness } from '$lib/api/client.js';
	import type { CompletenessResponse } from '$lib/api/types.js';
	import { formatFiscalMes } from '$lib/utils/format.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { AlertCircle, ChevronDown } from 'lucide-svelte';

	let { months, onselect }: {
		months: string[];
		onselect: (month: string) => void;
	} = $props();

	let incomplete = $state<CompletenessResponse[]>([]);
	let checking = $state(false);
	let failedMonths = $state<string[]>([]);
	let retry = $state(0);

	$effect(() => {
		const snapshot = [...months];
		void retry;
		let cancelled = false;
		checking = snapshot.length > 0;
		incomplete = [];
		failedMonths = [];
		void Promise.allSettled(snapshot.map(getCompleteness)).then((results) => {
			if (cancelled) return;
			const pending: CompletenessResponse[] = [];
			const failed: string[] = [];
			results.forEach((result, index) => {
				if (result.status === 'rejected') failed.push(snapshot[index]);
				else if (!result.value.month_complete) pending.push(result.value);
			});
			incomplete = pending.sort((a, b) => b.fiscal_mes.localeCompare(a.fiscal_mes));
			failedMonths = failed;
			checking = false;
		});
		return () => { cancelled = true; };
	});

	function missingDocuments(month: CompletenessResponse) {
		return [
			{ missing: !month.nfs_ok, label: `NFs (${month.nfs_count}/2)`, path: '/nfs' },
			{ missing: !month.boletos_ok, label: 'Boleto com recibo', path: '/boletos' },
			{ missing: !month.darfs_ok, label: 'DARF com recibo', path: '/darfs' },
			{ missing: month.irpj_csll_required && !month.irpj_csll_ok, label: 'IRPJ/CSLL com recibo', path: '/irpj-csll' },
			{ missing: !month.extratos_ok, label: 'Extrato', path: '/extratos' }
		].filter((document) => document.missing);
	}
</script>

<div aria-live="polite" hidden={!checking && incomplete.length === 0 && failedMonths.length === 0}>
	{#if checking}
		<p class="text-sm text-muted-foreground">Verificando pendências de todos os meses…</p>
	{:else if incomplete.length > 0 || failedMonths.length > 0}
		<details class="group rounded-lg border border-warning/20 bg-warning/5">
			<summary class="flex cursor-pointer list-none items-center gap-2.5 px-4 py-3 text-sm [&::-webkit-details-marker]:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
				<AlertCircle class="h-4 w-4 shrink-0 text-warning" />
				<span class="flex-1 font-medium">
					{#if incomplete.length > 0}
						{incomplete.length} {incomplete.length === 1 ? 'mês com pendências' : 'meses com pendências'}
					{:else}
						Não foi possível verificar todos os meses
					{/if}
				</span>
				{#if failedMonths.length > 0 && incomplete.length > 0}
					<span class="text-xs text-muted-foreground">Verificação incompleta</span>
				{/if}
				<span class="hidden text-xs text-muted-foreground sm:inline group-open:hidden">Ver pendências</span>
				<ChevronDown class="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
			</summary>
			<div class="space-y-3 border-t border-warning/15 px-4 py-3">
				{#if incomplete.length > 0}
					<ul class="divide-y divide-border">
						{#each incomplete as month (month.fiscal_mes)}
							<li class="flex flex-col gap-2 py-2 first:pt-0 last:pb-0 sm:flex-row sm:items-baseline sm:gap-4">
								<button type="button" onclick={() => onselect(month.fiscal_mes)} class="shrink-0 rounded-sm text-left text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
									{formatFiscalMes(month.fiscal_mes)}
								</button>
								<div class="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
									{#each missingDocuments(month) as document (document.path)}
										<a class="rounded-sm underline decoration-border underline-offset-4 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`${document.path}?fiscal_mes=${month.fiscal_mes}`}>
											{document.label}
										</a>
									{/each}
								</div>
							</li>
						{/each}
					</ul>
				{/if}
				{#if failedMonths.length > 0}
					<div class="space-y-2">
						<p class="text-sm text-muted-foreground">Não foi possível verificar: {failedMonths.map(formatFiscalMes).join(', ')}.</p>
						<Button variant="outline" size="sm" onclick={() => { retry += 1; }}>Tentar novamente</Button>
					</div>
				{/if}
			</div>
		</details>
	{/if}
</div>
