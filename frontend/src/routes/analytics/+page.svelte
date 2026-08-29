<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		formatApiErrorMessage,
		getFluxoSeries,
		getNfSeries,
		listDarfs,
		listIrpjCsll
	} from '$lib/api/client.js';
	import type { DarfEntry, FluxoSeriesPoint, IrpjCsllEntry, NfSeriesPoint } from '$lib/api/types.js';
	import { formatBrl, formatFiscalMes, formatUsd, formatNumber } from '$lib/utils/format.js';
	import AnalyticsLineChart, {
		type ChartPoint,
		type ChartSeries
	} from '$lib/components/AnalyticsLineChart.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Loader2, TrendingUp } from 'lucide-svelte';
	import { cn } from '$lib/utils.js';

	let dateFrom = $state('');
	let dateTo = $state('');
	let points = $state<NfSeriesPoint[]>([]);
	let darfEntries = $state<DarfEntry[]>([]);
	let irpjCsllEntries = $state<IrpjCsllEntry[]>([]);
	let loading = $state(false);
	let hasSearched = $state(false);
	let fluxoPoints = $state<FluxoSeriesPoint[]>([]);
	let requestSequence = 0;

	onMount(() => {
		const now = new Date();
		const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 3, 1);
		dateFrom = threeMonthsAgo.toISOString().split('T')[0];
		dateTo = now.toISOString().split('T')[0];
		void getFluxoSeries()
			.then((r) => (fluxoPoints = r.points))
			.catch(() => (fluxoPoints = []));
	});

	async function loadData() {
		if (!dateFrom || !dateTo) {
			toast.error('Both dates are required');
			return;
		}
		const requestId = ++requestSequence;
		loading = true;
		hasSearched = true;
		try {
			const [nfSeries, darfs, irpjCsll] = await Promise.all([
				getNfSeries(dateFrom, dateTo),
				listDarfs(),
				listIrpjCsll()
			]);
			if (requestId !== requestSequence) return;
			points = nfSeries.points;
			darfEntries = darfs;
			irpjCsllEntries = irpjCsll;
		} catch (e) {
			if (requestId !== requestSequence) return;
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load analytics'
			);
			points = [];
			darfEntries = [];
			irpjCsllEntries = [];
		} finally {
			if (requestId === requestSequence) {
				loading = false;
			}
		}
	}

	$effect(() => {
		if (dateFrom && dateTo) loadData();
	});

	type SummaryTableRow = {
		fiscalMes: string;
		monthlyTaxes: number;
		cumulativeTaxes: number;
		monthlyNfWithSpread: number;
		cumulativeNfWithSpread: number;
		cumulativeDifference: number;
	};

	const usdSeries: ChartSeries[] = [
		{ key: 'usd', label: 'USD', color: 'var(--color-chart-1)', format: formatUsd }
	];

	const brlSeries: ChartSeries[] = [
		{
			key: 'brl_no_spread',
			label: 'BRL (no spread)',
			color: 'var(--color-chart-2)',
			format: formatBrl
		},
		{
			key: 'brl_with_spread',
			label: 'BRL (with spread)',
			color: 'var(--color-chart-4)',
			format: formatBrl
		}
	];

	const rateSeries: ChartSeries[] = [
		{
			key: 'rate',
			label: 'Rate',
			color: 'var(--color-chart-1)',
			format: (value) => formatNumber(value, 4)
		},
		{
			key: 'effective_rate',
			label: 'Effective Rate',
			color: 'var(--color-chart-5)',
			format: (value) => formatNumber(value, 4)
		}
	];

	const legendClass = 'mt-4 flex flex-wrap items-center gap-4 text-xs font-medium text-foreground/90';
	const legendSwatchClass = 'inline-block h-2.5 w-5 rounded-full ring-1 ring-white/10';

	function parseInputDate(value: string): Date | null {
		if (!value) return null;
		const parsed = new Date(`${value}T00:00:00`);
		return Number.isNaN(parsed.getTime()) ? null : parsed;
	}

	function parseFiscalMes(value: string | null | undefined): Date | null {
		if (!value) return null;
		const match = /^(\d{4})-(\d{2})$/.exec(value);
		if (!match) return null;
		const [, year, month] = match;
		const parsed = new Date(Number(year), Number(month) - 1, 1);
		return Number.isNaN(parsed.getTime()) ? null : parsed;
	}

	function endOfMonth(value: Date): Date {
		return new Date(value.getFullYear(), value.getMonth() + 1, 0);
	}

	function startOfMonth(value: Date): Date {
		return new Date(value.getFullYear(), value.getMonth(), 1);
	}

	function toFiscalMesFromDate(value: Date): string {
		const year = value.getFullYear();
		const month = String(value.getMonth() + 1).padStart(2, '0');
		return `${year}-${month}`;
	}

	const chartData = $derived<ChartPoint[]>(
		points.map((p) => ({
			...p,
			date: new Date(p.date)
		}))
	);

	const summaryTableRows = $derived.by<SummaryTableRow[]>(() => {
		const monthStartBase = parseInputDate(dateFrom);
		const monthStart = monthStartBase ? startOfMonth(monthStartBase) : null;
		const monthEndBase = parseInputDate(dateTo);
		const monthEnd = monthEndBase ? endOfMonth(monthEndBase) : null;
		const monthlyTaxes = new Map<string, number>();
		const monthlyNfWithSpread = new Map<string, number>();

		for (const entry of [...darfEntries, ...irpjCsllEntries]) {
			if (!entry.fiscal_mes || entry.value == null) continue;
			const fiscalMesDate = parseFiscalMes(entry.fiscal_mes);
			if (!fiscalMesDate) continue;
			if (monthStart && fiscalMesDate < monthStart) continue;
			if (monthEnd && fiscalMesDate > monthEnd) continue;
			monthlyTaxes.set(entry.fiscal_mes, (monthlyTaxes.get(entry.fiscal_mes) ?? 0) + entry.value);
		}

		for (const point of points) {
			const parsedDate = new Date(point.date);
			if (Number.isNaN(parsedDate.getTime())) continue;
			const fiscalMes = toFiscalMesFromDate(parsedDate);
			monthlyNfWithSpread.set(
				fiscalMes,
				(monthlyNfWithSpread.get(fiscalMes) ?? 0) + point.brl_with_spread
			);
		}

		let cumulativeTaxes = 0;
		let cumulativeNfWithSpread = 0;
		return Array.from(new Set([...monthlyTaxes.keys(), ...monthlyNfWithSpread.keys()]))
			.sort((left, right) => left.localeCompare(right))
			.map((fiscalMes) => {
				const monthlyTaxValue = monthlyTaxes.get(fiscalMes) ?? 0;
				const monthlyNfValue = monthlyNfWithSpread.get(fiscalMes) ?? 0;
				cumulativeTaxes += monthlyTaxValue;
				cumulativeNfWithSpread += monthlyNfValue;
				return {
					fiscalMes,
					monthlyTaxes: monthlyTaxValue,
					cumulativeTaxes,
					monthlyNfWithSpread: monthlyNfValue,
					cumulativeNfWithSpread,
					cumulativeDifference: cumulativeNfWithSpread - cumulativeTaxes
				};
			});
	});

	const hasAnyChartData = $derived(chartData.length > 0 || summaryTableRows.length > 0);
</script>

<div class="space-y-6">
	<PageHeader title="Analytics" description="NF, impostos e saques vs casa" />

	{#if fluxoPoints.length > 0}
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-sm">Saques vs sua parte da casa</Card.Title>
				<Card.Description>Por mês fiscal — saques da PJ e necessidade da casa (sua parte).</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="rounded-lg border">
					<Table.Table>
						<Table.TableHeader>
							<Table.TableRow>
								<Table.TableHead>Mês</Table.TableHead>
								<Table.TableHead class="text-right">Saques</Table.TableHead>
								<Table.TableHead class="text-right">Sua parte casa</Table.TableHead>
								<Table.TableHead class="text-right">Diferença</Table.TableHead>
								<Table.TableHead>Casa</Table.TableHead>
							</Table.TableRow>
						</Table.TableHeader>
						<Table.TableBody>
							{#each fluxoPoints as row (row.fiscal_mes)}
								<Table.TableRow>
									<Table.TableCell>{formatFiscalMes(row.fiscal_mes)}</Table.TableCell>
									<Table.TableCell class="text-right tabular-nums">
										{formatBrl(row.saques_brl)}
									</Table.TableCell>
									<Table.TableCell class="text-right tabular-nums">
										{formatBrl(row.primary_share_brl)}
									</Table.TableCell>
									<Table.TableCell
										class={cn(
											'text-right tabular-nums',
											row.saques_brl >= row.primary_share_brl
												? 'text-emerald-400'
												: 'text-amber-400'
										)}
									>
										{formatBrl(row.saques_brl - row.primary_share_brl)}
									</Table.TableCell>
									<Table.TableCell>
										{row.casa_saved ? 'salva' : 'estimada'}
									</Table.TableCell>
								</Table.TableRow>
							{/each}
						</Table.TableBody>
					</Table.Table>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- Date range -->
	<div class="flex flex-wrap items-end gap-3">
		<div class="space-y-1">
			<span class="text-xs font-medium text-muted-foreground">From</span>
			<Input type="date" bind:value={dateFrom} class="w-40" />
		</div>
		<div class="space-y-1">
			<span class="text-xs font-medium text-muted-foreground">To</span>
			<Input type="date" bind:value={dateTo} class="w-40" />
		</div>
		<Button onclick={loadData} disabled={loading} variant="outline">
			{#if loading}
				<Loader2 class="h-4 w-4 animate-spin" />
			{/if}
			Load
		</Button>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
		</div>
	{:else if hasSearched && !hasAnyChartData}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<TrendingUp class="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
				<p class="text-muted-foreground">No data found in the selected date range.</p>
			</Card.Content>
		</Card.Root>
	{:else if hasAnyChartData}
		{#if summaryTableRows.length > 0}
			<Card.Root>
				<Card.Header>
					<Card.Title class="text-sm">Monthly Tax and NF Summary</Card.Title>
					<Card.Description>
						DARF and IRPJ/CSLL taxes plus NF totals with spread, grouped by month
					</Card.Description>
				</Card.Header>
				<Card.Content>
					<div class="rounded-lg border">
						<Table.Table>
							<Table.TableHeader>
								<Table.TableRow>
									<Table.TableHead>Fiscal month</Table.TableHead>
									<Table.TableHead class="text-right">Monthly taxes</Table.TableHead>
									<Table.TableHead class="text-right">Accumulated taxes</Table.TableHead>
									<Table.TableHead class="text-right">Monthly NF (with spread)</Table.TableHead>
									<Table.TableHead class="text-right">Accumulated NF (with spread)</Table.TableHead>
									<Table.TableHead class="text-right">Accumulated difference</Table.TableHead>
								</Table.TableRow>
							</Table.TableHeader>
							<Table.TableBody>
								{#each summaryTableRows as row (row.fiscalMes)}
									<Table.TableRow>
										<Table.TableCell>{formatFiscalMes(row.fiscalMes)}</Table.TableCell>
										<Table.TableCell class="text-right tabular-nums">
											{formatBrl(row.monthlyTaxes)}
										</Table.TableCell>
										<Table.TableCell class="text-right tabular-nums">
											{formatBrl(row.cumulativeTaxes)}
										</Table.TableCell>
										<Table.TableCell class="text-right tabular-nums">
											{formatBrl(row.monthlyNfWithSpread)}
										</Table.TableCell>
										<Table.TableCell class="text-right tabular-nums">
											{formatBrl(row.cumulativeNfWithSpread)}
										</Table.TableCell>
										<Table.TableCell class="text-right tabular-nums">
											{formatBrl(row.cumulativeDifference)}
										</Table.TableCell>
									</Table.TableRow>
								{/each}
							</Table.TableBody>
						</Table.Table>
					</div>
				</Card.Content>
			</Card.Root>
		{/if}

		{#if chartData.length > 0}
			<!-- USD Chart -->
			<Card.Root>
				<Card.Header>
					<Card.Title class="text-sm">USD over Time</Card.Title>
				</Card.Header>
				<Card.Content class="space-y-4">
					<AnalyticsLineChart data={chartData} series={usdSeries} yTickFormat={formatUsd} />
				</Card.Content>
			</Card.Root>

			<!-- BRL Chart -->
			<Card.Root>
				<Card.Header>
					<Card.Title class="text-sm">BRL over Time</Card.Title>
					<Card.Description>No spread vs. with spread</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<AnalyticsLineChart
						data={chartData}
						series={brlSeries}
						yTickFormat={formatBrl}
						yPaddingLeft={64}
					/>
					<div class={legendClass}>
						<span class="flex items-center gap-2">
							<span class={`${legendSwatchClass} bg-chart-2`}></span>
							No spread
						</span>
						<span class="flex items-center gap-2">
							<span class={`${legendSwatchClass} bg-chart-4`}></span>
							With spread
						</span>
					</div>
				</Card.Content>
			</Card.Root>

			<!-- Rate Chart -->
			<Card.Root>
				<Card.Header>
					<Card.Title class="text-sm">Exchange Rate over Time</Card.Title>
					<Card.Description>Rate vs. effective rate</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<AnalyticsLineChart
						data={chartData}
						series={rateSeries}
						yTickFormat={(value) => formatNumber(value, 4)}
					/>
					<div class={legendClass}>
						<span class="flex items-center gap-2">
							<span class={`${legendSwatchClass} bg-chart-1`}></span>
							Rate
						</span>
						<span class="flex items-center gap-2">
							<span class={`${legendSwatchClass} bg-chart-5`}></span>
							Effective Rate
						</span>
					</div>
				</Card.Content>
			</Card.Root>
		{/if}
	{/if}
</div>
