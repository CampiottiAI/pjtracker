<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { scaleTime, scaleLinear } from 'd3-scale';
	import { Chart, Svg, Axis, Spline, Highlight, Tooltip } from 'layerchart';
	import {
		ApiError,
		formatApiErrorMessage,
		getNfSeries
	} from '$lib/api/client.js';
	import type { NfSeriesPoint } from '$lib/api/types.js';
	import { formatBrl, formatUsd, formatNumber } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Loader2, TrendingUp } from 'lucide-svelte';

	let dateFrom = $state('');
	let dateTo = $state('');
	let points = $state<NfSeriesPoint[]>([]);
	let loading = $state(false);
	let hasSearched = $state(false);

	onMount(() => {
		const now = new Date();
		const threeMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 3, 1);
		dateFrom = threeMonthsAgo.toISOString().split('T')[0];
		dateTo = now.toISOString().split('T')[0];
	});

	async function loadData() {
		if (!dateFrom || !dateTo) {
			toast.error('Both dates are required');
			return;
		}
		loading = true;
		hasSearched = true;
		try {
			const res = await getNfSeries(dateFrom, dateTo);
			points = res.points;
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load analytics'
			);
			points = [];
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (dateFrom && dateTo) loadData();
	});

	type ChartPoint = {
		date: Date;
		[key: string]: unknown;
	};

	const chartFrameClass =
		'analytics-chart h-64 rounded-xl border border-border/70 bg-background/40 px-3 pt-3 pb-2 shadow-inner shadow-black/25';
	const tooltipCardClass =
		'min-w-44 rounded-lg border border-border/80 bg-card/95 px-3 py-2 text-xs text-card-foreground shadow-2xl backdrop-blur-sm';
	const tooltipHeaderClass =
		'mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground';
	const tooltipRowClass = 'flex items-center justify-between gap-4';
	const tooltipLabelClass = 'flex items-center gap-2 text-muted-foreground';
	const tooltipValueClass = 'font-semibold text-card-foreground';
	const legendClass = 'mt-4 flex flex-wrap items-center gap-4 text-xs font-medium text-foreground/90';
	const legendSwatchClass = 'inline-block h-2.5 w-5 rounded-full ring-1 ring-white/10';

	const chartData = $derived<ChartPoint[]>(
		points.map((p) => ({
			...p,
			date: new Date(p.date)
		}))
	);
</script>

<div class="space-y-6">
	<PageHeader title="Analytics" description="NF time series and financial charts" />

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
	{:else if hasSearched && points.length === 0}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<TrendingUp class="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
				<p class="text-muted-foreground">No data found in the selected date range.</p>
			</Card.Content>
		</Card.Root>
	{:else if chartData.length > 0}
		<!-- USD Chart -->
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-sm">USD over Time</Card.Title>
			</Card.Header>
			<Card.Content class="space-y-4">
				<div class={chartFrameClass}>
					<Chart
						data={chartData}
						x="date"
						xScale={scaleTime()}
						y="usd"
						yScale={scaleLinear()}
						yNice
						padding={{ left: 56, bottom: 30, top: 14, right: 18 }}
					>
						<Svg>
							<Axis placement="left" format={(v) => formatUsd(v)} grid rule />
							<Axis placement="bottom" rule />
							<Spline class="stroke-chart-1 stroke-[2.5]" />
							<Highlight points lines />
						</Svg>
						<Tooltip.Root x="data" y="pointer" let:data>
							<div class={tooltipCardClass}>
								<p class={tooltipHeaderClass}>{data.date?.toLocaleDateString('pt-BR')}</p>
								<div class="space-y-1.5">
									<div class={tooltipRowClass}>
										<span class={tooltipLabelClass}>
											<span class="h-2.5 w-2.5 rounded-full bg-chart-1"></span>
											USD
										</span>
										<span class={tooltipValueClass}>{formatUsd(data.usd)}</span>
									</div>
								</div>
							</div>
						</Tooltip.Root>
					</Chart>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- BRL Chart -->
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-sm">BRL over Time</Card.Title>
				<Card.Description>No spread vs. with spread</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-4">
				<div class={chartFrameClass}>
					<Chart
						data={chartData}
						x="date"
						xScale={scaleTime()}
						y={['brl_no_spread', 'brl_with_spread']}
						yScale={scaleLinear()}
						yNice
						padding={{ left: 64, bottom: 30, top: 14, right: 18 }}
					>
						<Svg>
							<Axis placement="left" format={(v) => formatBrl(v)} grid rule />
							<Axis placement="bottom" rule />
							<Spline y="brl_no_spread" class="stroke-chart-2 stroke-[2.5]" />
							<Spline y="brl_with_spread" class="stroke-chart-4 stroke-[2.5]" />
							<Highlight points lines />
						</Svg>
						<Tooltip.Root x="data" y="pointer" let:data>
							<div class={tooltipCardClass}>
								<p class={tooltipHeaderClass}>{data.date?.toLocaleDateString('pt-BR')}</p>
								<div class="space-y-1.5">
									<div class={tooltipRowClass}>
										<span class={tooltipLabelClass}>
											<span class="h-2.5 w-2.5 rounded-full bg-chart-2"></span>
											BRL (no spread)
										</span>
										<span class={tooltipValueClass}>{formatBrl(data.brl_no_spread)}</span>
									</div>
									<div class={tooltipRowClass}>
										<span class={tooltipLabelClass}>
											<span class="h-2.5 w-2.5 rounded-full bg-chart-4"></span>
											BRL (with spread)
										</span>
										<span class={tooltipValueClass}>{formatBrl(data.brl_with_spread)}</span>
									</div>
								</div>
							</div>
						</Tooltip.Root>
					</Chart>
				</div>
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
				<div class={chartFrameClass}>
					<Chart
						data={chartData}
						x="date"
						xScale={scaleTime()}
						y={['rate', 'effective_rate']}
						yScale={scaleLinear()}
						yNice
						padding={{ left: 56, bottom: 30, top: 14, right: 18 }}
					>
						<Svg>
							<Axis placement="left" format={(v) => formatNumber(v, 4)} grid rule />
							<Axis placement="bottom" rule />
							<Spline y="rate" class="stroke-chart-1 stroke-[2.5]" />
							<Spline y="effective_rate" class="stroke-chart-5 stroke-[2.5]" />
							<Highlight points lines />
						</Svg>
						<Tooltip.Root x="data" y="pointer" let:data>
							<div class={tooltipCardClass}>
								<p class={tooltipHeaderClass}>{data.date?.toLocaleDateString('pt-BR')}</p>
								<div class="space-y-1.5">
									<div class={tooltipRowClass}>
										<span class={tooltipLabelClass}>
											<span class="h-2.5 w-2.5 rounded-full bg-chart-1"></span>
											Rate
										</span>
										<span class={tooltipValueClass}>{formatNumber(data.rate, 4)}</span>
									</div>
									<div class={tooltipRowClass}>
										<span class={tooltipLabelClass}>
											<span class="h-2.5 w-2.5 rounded-full bg-chart-5"></span>
											Effective Rate
										</span>
										<span class={tooltipValueClass}>{formatNumber(data.effective_rate, 4)}</span>
									</div>
								</div>
							</div>
						</Tooltip.Root>
					</Chart>
				</div>
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
</div>

<style>
	.analytics-chart :global(svg) {
		overflow: visible;
	}

	.analytics-chart :global(svg text),
	.analytics-chart :global(.tick text),
	.analytics-chart :global([class*='axis'] text) {
		fill: var(--color-foreground) !important;
		font-size: 0.75rem;
	}

	.analytics-chart :global(svg .domain),
	.analytics-chart :global(svg .tick line),
	.analytics-chart :global(svg [class*='axis'] line),
	.analytics-chart :global(svg [class*='axis'] path) {
		stroke: color-mix(in oklab, var(--color-border) 75%, white 25%) !important;
	}

	.analytics-chart :global(.grid line),
	.analytics-chart :global(.grid path) {
		stroke: color-mix(in oklab, var(--color-border) 72%, transparent);
		stroke-dasharray: 3 5;
	}
</style>
