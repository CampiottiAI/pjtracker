<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { scaleTime, scaleLinear } from 'd3-scale';
	import { Chart, Svg, Axis, Spline, Highlight, Tooltip, Grid } from 'layerchart';
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
			<Card.Content>
				<div class="h-64">
					<Chart
						data={chartData}
						x="date"
						xScale={scaleTime()}
						y="usd"
						yScale={scaleLinear()}
						yNice
						padding={{ left: 48, bottom: 24, top: 8, right: 16 }}
					>
						<Svg>
							<Axis placement="left" format={(v) => formatUsd(v)} />
							<Axis placement="bottom" />
							<Grid />
							<Spline class="stroke-chart-1 stroke-2" />
							<Highlight points lines />
						</Svg>
						<Tooltip.Root let:data>
							<Tooltip.Header>
								{data.date?.toLocaleDateString('pt-BR')}
							</Tooltip.Header>
							<Tooltip.List>
								<Tooltip.Item label="USD" value={formatUsd(data.usd)} />
							</Tooltip.List>
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
			<Card.Content>
				<div class="h-64">
					<Chart
						data={chartData}
						x="date"
						xScale={scaleTime()}
						y={['brl_no_spread', 'brl_with_spread']}
						yScale={scaleLinear()}
						yNice
						padding={{ left: 56, bottom: 24, top: 8, right: 16 }}
					>
						<Svg>
							<Axis placement="left" format={(v) => formatBrl(v)} />
							<Axis placement="bottom" />
							<Grid />
							<Spline y="brl_no_spread" class="stroke-chart-2 stroke-2" />
							<Spline y="brl_with_spread" class="stroke-chart-4 stroke-2" />
							<Highlight points lines />
						</Svg>
						<Tooltip.Root let:data>
							<Tooltip.Header>
								{data.date?.toLocaleDateString('pt-BR')}
							</Tooltip.Header>
							<Tooltip.List>
								<Tooltip.Item label="BRL (no spread)" value={formatBrl(data.brl_no_spread)} />
								<Tooltip.Item label="BRL (with spread)" value={formatBrl(data.brl_with_spread)} />
							</Tooltip.List>
						</Tooltip.Root>
					</Chart>
				</div>
				<div class="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
					<span class="flex items-center gap-1"><span class="inline-block h-2 w-4 rounded bg-chart-2"></span> No spread</span>
					<span class="flex items-center gap-1"><span class="inline-block h-2 w-4 rounded bg-chart-4"></span> With spread</span>
				</div>
			</Card.Content>
		</Card.Root>

		<!-- Rate Chart -->
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-sm">Exchange Rate over Time</Card.Title>
				<Card.Description>Rate vs. effective rate</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="h-64">
					<Chart
						data={chartData}
						x="date"
						xScale={scaleTime()}
						y={['rate', 'effective_rate']}
						yScale={scaleLinear()}
						yNice
						padding={{ left: 48, bottom: 24, top: 8, right: 16 }}
					>
						<Svg>
							<Axis placement="left" format={(v) => formatNumber(v, 4)} />
							<Axis placement="bottom" />
							<Grid />
							<Spline y="rate" class="stroke-chart-1 stroke-2" />
							<Spline y="effective_rate" class="stroke-chart-5 stroke-2" />
							<Highlight points lines />
						</Svg>
						<Tooltip.Root let:data>
							<Tooltip.Header>
								{data.date?.toLocaleDateString('pt-BR')}
							</Tooltip.Header>
							<Tooltip.List>
								<Tooltip.Item label="Rate" value={formatNumber(data.rate, 4)} />
								<Tooltip.Item label="Effective Rate" value={formatNumber(data.effective_rate, 4)} />
							</Tooltip.List>
						</Tooltip.Root>
					</Chart>
				</div>
				<div class="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
					<span class="flex items-center gap-1"><span class="inline-block h-2 w-4 rounded bg-chart-1"></span> Rate</span>
					<span class="flex items-center gap-1"><span class="inline-block h-2 w-4 rounded bg-chart-5"></span> Effective Rate</span>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}
</div>
