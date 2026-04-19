<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		createFiscalMonth,
		listFiscalMonths,
		getCompleteness,
		formatApiErrorMessage
	} from '$lib/api/client.js';
	import type { CompletenessResponse } from '$lib/api/types.js';
	import { cn } from '$lib/utils.js';
	import { formatFiscalMes } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import {
		FileText,
		Receipt,
		Landmark,
		WalletCards,
		DollarSign,
		CheckCircle2,
		AlertCircle,
		Plus
	} from 'lucide-svelte';

	let months = $state<string[]>([]);
	let selectedMonth = $state('');
	let completeness = $state<CompletenessResponse | null>(null);
	let loading = $state(true);
	let createDialogOpen = $state(false);
	let createMonthValue = $state('');
	let creatingMonth = $state(false);

	onMount(async () => {
		try {
			await loadMonths();
		} catch (e) {
			const msg = e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load';
			toast.error(msg);
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!selectedMonth) {
			completeness = null;
			return;
		}
		loadCompleteness(selectedMonth);
	});

	async function loadCompleteness(fm: string) {
		try {
			completeness = await getCompleteness(fm);
		} catch (e) {
			completeness = null;
			if (e instanceof ApiError && e.status !== 422) {
				toast.error(formatApiErrorMessage(e.body));
			}
		}
	}

	async function loadMonths(preferredMonth?: string) {
		const res = await listFiscalMonths();
		months = res.months;
		if (months.length === 0) {
			selectedMonth = '';
			completeness = null;
			return;
		}
		if (preferredMonth && months.includes(preferredMonth)) {
			selectedMonth = preferredMonth;
			return;
		}
		if (selectedMonth && months.includes(selectedMonth)) {
			return;
		}
		selectedMonth = months[0];
	}

	function getCurrentMonthValue(): string {
		const today = new Date();
		const month = `${today.getMonth() + 1}`.padStart(2, '0');
		return `${today.getFullYear()}-${month}`;
	}

	function openCreateMonthDialog() {
		createMonthValue = selectedMonth || getCurrentMonthValue();
		createDialogOpen = true;
	}

	async function handleCreateMonth() {
		if (!createMonthValue) {
			toast.error('Select a fiscal month');
			return;
		}
		creatingMonth = true;
		try {
			const response = await createFiscalMonth(createMonthValue);
			await loadMonths(createMonthValue);
			createDialogOpen = false;
			toast.success(
				response.created
					? `${formatFiscalMes(createMonthValue)} created`
					: `${formatFiscalMes(createMonthValue)} already exists`
			);
		} catch (e) {
			const msg =
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to create fiscal month';
			toast.error(msg);
		} finally {
			creatingMonth = false;
		}
	}

	function handleCreateMonthSubmit(event: SubmitEvent) {
		event.preventDefault();
		void handleCreateMonth();
	}

	type CheckItem = {
		label: string;
		icon: typeof FileText;
		count: number;
		ok: boolean;
		required: number;
		href: string;
		optional?: boolean;
	};

	const checks = $derived<CheckItem[]>(
		completeness
			? [
					{
						label: 'Notas Fiscais',
						icon: FileText,
						count: completeness.nfs_count,
						ok: completeness.nfs_ok,
						required: 2,
						href: `/nfs?fiscal_mes=${selectedMonth}`
					},
					{
						label: 'Boletos c/ Recibo',
						icon: Receipt,
						count: completeness.boletos_with_receipt_count,
						ok: completeness.boletos_ok,
						required: 1,
						href: `/boletos?fiscal_mes=${selectedMonth}`
					},
					{
						label: 'DARFs c/ Recibo',
						icon: Landmark,
						count: completeness.darfs_with_receipt_count,
						ok: completeness.darfs_ok,
						required: 1,
						href: `/darfs?fiscal_mes=${selectedMonth}`
					},
					...(completeness.irpj_csll_required
						? [
								{
									label: 'IRPJ/CSLL c/ Recibo',
									icon: Landmark,
									count: completeness.irpj_csll_with_receipt_count,
									ok: completeness.irpj_csll_ok,
									required: 1,
									href: `/irpj-csll?fiscal_mes=${selectedMonth}`
								}
							]
						: []),
					{
						label: 'Extratos c/ Caixinha',
						icon: WalletCards,
						count: completeness.extratos_caixinha_count,
						ok: completeness.extratos_ok,
						required: 1,
						href: `/extratos?fiscal_mes=${selectedMonth}`
					},
					{
						label: 'Higlobe',
						icon: DollarSign,
						count: completeness.extratos_higlobe_count,
						ok: completeness.higlobe_ok,
						required: 1,
						href: `/extratos?fiscal_mes=${selectedMonth}`,
						optional: true
					}
				]
			: []
	);
</script>

<div class="space-y-6">
	<PageHeader title="Dashboard" description="Fiscal month completeness overview">
		{#snippet actions()}
			<Button onclick={openCreateMonthDialog}>
				<Plus class="h-4 w-4" />
				Create fiscal month
			</Button>
		{/snippet}
	</PageHeader>

	<!-- Month selector -->
	<div class="flex items-center gap-3">
		<label for="month-select" class="text-sm font-medium text-muted-foreground">Fiscal Month</label>
		{#if loading}
			<div class="h-9 w-40 animate-pulse rounded-md bg-muted"></div>
		{:else if months.length > 0}
			<select
				id="month-select"
				class="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
				bind:value={selectedMonth}
			>
				{#each months as m}
					<option value={m}>{formatFiscalMes(m)}</option>
				{/each}
			</select>
		{:else}
			<span class="text-sm text-muted-foreground">No fiscal months found</span>
		{/if}
	</div>

	<!-- Overall status -->
	{#if completeness}
		{@const complete = completeness.month_complete}
		<div
			class={cn(
				'flex items-center gap-3 rounded-lg border px-4 py-3',
				complete
					? 'border-emerald-500/30 bg-emerald-500/5'
					: 'border-amber-500/30 bg-amber-500/5'
			)}
		>
			{#if complete}
				<CheckCircle2 class="h-5 w-5 text-emerald-400" />
				<span class="text-sm font-medium text-emerald-400">
					{formatFiscalMes(selectedMonth)} is complete
				</span>
			{:else}
				<AlertCircle class="h-5 w-5 text-amber-400" />
				<span class="text-sm font-medium text-amber-400">
					{formatFiscalMes(selectedMonth)} has missing items
				</span>
			{/if}
		</div>
	{/if}

	<!-- Completeness cards -->
	{#if completeness}
		<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
			{#each checks as item}
				<a href={item.href} class="block group">
					<Card.Root
						class="transition-colors group-hover:border-muted-foreground/30 h-full"
					>
						<Card.Header class="pb-2">
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-2 text-muted-foreground">
									<item.icon class="h-4 w-4" />
									<Card.Title class="text-sm font-medium">{item.label}</Card.Title>
								</div>
								{#if item.optional}
									<Badge variant="outline" class="text-[10px] px-1.5 py-0">optional</Badge>
								{/if}
							</div>
						</Card.Header>
						<Card.Content>
							<div class="flex items-end justify-between">
								<span class="text-3xl font-bold tabular-nums">
									{item.count}
									<span class="text-lg text-muted-foreground font-normal">
										/ {item.required}
									</span>
								</span>
								{#if item.ok}
									<CheckCircle2 class="h-5 w-5 text-emerald-400" />
								{:else}
									<AlertCircle class="h-5 w-5 text-amber-400" />
								{/if}
							</div>
						</Card.Content>
					</Card.Root>
				</a>
			{/each}
		</div>
	{/if}

	{#if !loading && months.length === 0}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<FileText class="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
				<p class="text-muted-foreground">No data yet. Start by uploading documents.</p>
			</Card.Content>
		</Card.Root>
	{/if}
</div>

<Dialog.Root bind:open={createDialogOpen}>
	<Dialog.Content>
		<form class="space-y-4" onsubmit={handleCreateMonthSubmit}>
			<Dialog.Header>
				<Dialog.Title>Create fiscal month</Dialog.Title>
				<Dialog.Description>
					Create an empty fiscal month so it appears on the dashboard before any uploads.
				</Dialog.Description>
			</Dialog.Header>

			<div class="space-y-2">
				<label for="create-fiscal-month" class="text-sm font-medium">Fiscal month</label>
				<Input id="create-fiscal-month" type="month" bind:value={createMonthValue} required />
			</div>

			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (createDialogOpen = false)}>
					Cancel
				</Button>
				<Button type="submit" disabled={creatingMonth}>
					{creatingMonth ? 'Creating...' : 'Create'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>
