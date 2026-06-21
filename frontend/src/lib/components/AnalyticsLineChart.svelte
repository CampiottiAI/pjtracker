<script lang="ts">
	import { browser } from '$app/environment';
	import { VisXYContainer, VisLine, VisAxis, VisCrosshair, VisTooltip } from '@unovis/svelte';

	export type ChartPoint = {
		date: Date;
		[key: string]: unknown;
	};

	export type ChartSeries = {
		key: string;
		label: string;
		color: string;
		format: (value: number) => string;
	};

	interface Props {
		data: ChartPoint[];
		series: ChartSeries[];
		yTickFormat: (value: number) => string;
		height?: number;
		yPaddingLeft?: number;
	}

	let {
		data,
		series,
		yTickFormat,
		height = 320,
		yPaddingLeft = 56
	}: Props = $props();

	const x = (d: ChartPoint) => d.date.getTime();
	const y = $derived.by(() =>
		series.length === 1
			? (d: ChartPoint) => d[series[0].key] as number
			: series.map((s) => (d: ChartPoint) => d[s.key] as number)
	);
	const color = $derived.by(
		() => (_d: ChartPoint, i: number) => series[i]?.color ?? series[0].color
	);

	function formatXTick(tick: number | Date): string {
		const date = tick instanceof Date ? tick : new Date(tick);
		return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
	}

	function formatYTick(tick: number | Date): string {
		return yTickFormat(tick as number);
	}

	function crosshairTemplate(datum: ChartPoint | undefined): string {
		if (!datum) return '';

		const header = `<p class="analytics-tooltip-header">${datum.date.toLocaleDateString('pt-BR')}</p>`;
		const rows = series
			.map((s) => {
				const value = datum[s.key] as number;
				return `<div class="analytics-tooltip-row">
					<span class="analytics-tooltip-label">
						<span class="analytics-tooltip-swatch" style="background-color:${s.color}"></span>
						${s.label}
					</span>
					<span class="analytics-tooltip-value">${s.format(value)}</span>
				</div>`;
			})
			.join('');

		return `<div class="analytics-tooltip">${header}<div class="analytics-tooltip-rows">${rows}</div></div>`;
	}

	const chartKey = $derived(
		data.length > 0
			? `${data.length}-${data[0]?.date?.getTime()}-${data[data.length - 1]?.date?.getTime()}`
			: 'empty'
	);

	const tooltipContainer = browser ? document.body : undefined;
</script>

<div class="analytics-chart rounded-xl border border-border/70 bg-background/40 px-3 pt-3 pb-2 shadow-inner shadow-black/25">
	{#key chartKey}
		<VisXYContainer
			{data}
			{height}
			padding={{ top: 14, bottom: 30, left: yPaddingLeft, right: 18 }}
		>
			<VisLine {x} {y} {color} lineWidth={2.5} />
			<VisAxis
				type="x"
				tickFormat={formatXTick}
				tickTextColor="var(--color-foreground)"
				tickTextFontSize="12px"
				domainLine
				gridLine={false}
			/>
			<VisAxis
				type="y"
				tickFormat={formatYTick}
				tickTextColor="var(--color-foreground)"
				tickTextFontSize="12px"
				gridLine
				domainLine
			/>
			<VisCrosshair {x} {y} template={crosshairTemplate} color={color} />
			<VisTooltip container={tooltipContainer} className="analytics-unovis-tooltip" />
		</VisXYContainer>
	{/key}
</div>

<style>
	.analytics-chart {
		--vis-axis-tick-color: color-mix(in oklab, var(--color-border) 75%, white 25%);
		--vis-axis-tick-label-color: var(--color-foreground);
		--vis-axis-domain-color: color-mix(in oklab, var(--color-border) 75%, white 25%);
		--vis-axis-grid-color: color-mix(in oklab, var(--color-border) 72%, transparent);
		--vis-axis-grid-line-dasharray: 3 5;
		--vis-crosshair-line-stroke-color: color-mix(in oklab, var(--color-border) 80%, white 20%);
		--vis-crosshair-circle-stroke-color: var(--color-background);
	}

	:global(.analytics-unovis-tooltip) {
		z-index: 50;
	}

	:global(.analytics-tooltip) {
		min-width: 11rem;
		border-radius: 0.5rem;
		border: 1px solid color-mix(in oklab, var(--color-border) 80%, transparent);
		background: color-mix(in oklab, var(--color-card) 95%, transparent);
		padding: 0.5rem 0.75rem;
		font-size: 0.75rem;
		color: var(--color-card-foreground);
		box-shadow: 0 25px 50px -12px rgb(0 0 0 / 0.25);
		backdrop-filter: blur(4px);
	}

	:global(.analytics-tooltip-header) {
		margin: 0 0 0.5rem;
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--color-muted-foreground);
	}

	:global(.analytics-tooltip-rows) {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	:global(.analytics-tooltip-row) {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
	}

	:global(.analytics-tooltip-label) {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		color: var(--color-muted-foreground);
	}

	:global(.analytics-tooltip-swatch) {
		display: inline-block;
		height: 0.625rem;
		width: 0.625rem;
		border-radius: 9999px;
	}

	:global(.analytics-tooltip-value) {
		font-weight: 600;
		color: var(--color-card-foreground);
	}
</style>
