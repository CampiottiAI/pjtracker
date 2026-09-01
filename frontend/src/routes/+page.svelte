<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		createFiscalMonth,
		createWithdraw,
		deleteWithdraw,
		downloadFiscalMonthPack,
		formatApiErrorMessage,
		getFluxo,
		listFiscalMonths,
		listWithdraws,
		triggerDownload,
		updateWithdraw
	} from '$lib/api/client.js';
	import type {
		FluxoResponse,
		WithdrawEntry,
		WithdrawSummary
	} from '$lib/api/types.js';
	import { cn } from '$lib/utils.js';
	import { formatFiscalMes, formatBrl, formatWithdrawDate } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
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
		Plus,
		Pencil,
		Trash2,
		Banknote,
		Home,
		Building2,
		Download
	} from 'lucide-svelte';

	let months = $state<string[]>([]);
	let selectedMonth = $state('');
	let fluxo = $state<FluxoResponse | null>(null);
	let withdrawItems = $state<WithdrawEntry[]>([]);
	let withdrawSummary = $state<WithdrawSummary | null>(null);
	let withdrawLoading = $state(false);
	let loading = $state(true);

	let createDialogOpen = $state(false);
	let createMonthValue = $state('');
	let creatingMonth = $state(false);

	let addWithdrawDate = $state('');
	let addWithdrawAmount = $state('');
	let addWithdrawNotes = $state('');
	let addingWithdraw = $state(false);

	let editDialogOpen = $state(false);
	let editingWithdraw = $state<WithdrawEntry | null>(null);
	let editWithdrawDate = $state('');
	let editWithdrawAmount = $state('');
	let editWithdrawNotes = $state('');
	let savingWithdraw = $state(false);

	let deleteDialogOpen = $state(false);
	let deletingWithdraw = $state<WithdrawEntry | null>(null);
	let downloadingPack = $state(false);

	const WITHDRAW_TARGET_BRL = 50_000;

	function emptyWithdrawSummary(): WithdrawSummary {
		return {
			target_brl: WITHDRAW_TARGET_BRL,
			total_brl: 0,
			remaining_brl: WITHDRAW_TARGET_BRL,
			over_target_brl: 0,
			target_reached: false,
			previous_month_income_brl: 0
		};
	}

	function getTodayIsoDate(): string {
		const today = new Date();
		return `${today.getFullYear()}-${`${today.getMonth() + 1}`.padStart(2, '0')}-${`${today.getDate()}`.padStart(2, '0')}`;
	}

	function parseAmountInput(value: string | number | null | undefined): number | null {
		if (value == null) return null;
		let raw = String(value).trim();
		if (!raw) return null;
		if (raw.includes(',')) raw = raw.replace(/\./g, '').replace(',', '.');
		const amount = Number.parseFloat(raw);
		if (!Number.isFinite(amount) || amount <= 0) return null;
		return amount;
	}

	function resetAddWithdrawForm() {
		addWithdrawDate = getTodayIsoDate();
		addWithdrawAmount = '';
		addWithdrawNotes = '';
	}

	onMount(async () => {
		resetAddWithdrawForm();
		try {
			await loadMonths();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar');
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!selectedMonth) {
			fluxo = null;
			withdrawItems = [];
			withdrawSummary = null;
			return;
		}
		addWithdrawDate = getTodayIsoDate();
		void loadFluxo(selectedMonth);
		void loadWithdraws(selectedMonth);
	});

	async function loadFluxo(fm: string) {
		try {
			fluxo = await getFluxo(fm);
		} catch (e) {
			fluxo = null;
			if (e instanceof ApiError && e.status !== 422) {
				toast.error(formatApiErrorMessage(e.body));
			}
		}
	}

	async function loadWithdraws(fm: string) {
		withdrawLoading = true;
		try {
			const response = await listWithdraws(fm);
			withdrawItems = response.items;
			withdrawSummary = response.summary;
		} catch (e) {
			withdrawItems = [];
			withdrawSummary = emptyWithdrawSummary();
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar saques'
			);
		} finally {
			withdrawLoading = false;
		}
	}

	async function loadMonths(preferredMonth?: string) {
		const res = await listFiscalMonths();
		months = res.months;
		if (months.length === 0) {
			selectedMonth = '';
			return;
		}
		if (preferredMonth && months.includes(preferredMonth)) {
			selectedMonth = preferredMonth;
			return;
		}
		if (selectedMonth && months.includes(selectedMonth)) return;
		selectedMonth = months[0];
	}

	function getCurrentMonthValue(): string {
		const today = new Date();
		return `${today.getFullYear()}-${`${today.getMonth() + 1}`.padStart(2, '0')}`;
	}

	async function handleAddWithdraw(event: SubmitEvent) {
		event.preventDefault();
		if (!selectedMonth) return;
		const amount = parseAmountInput(addWithdrawAmount);
		if (!addWithdrawDate) {
			toast.error('Informe a data do saque');
			return;
		}
		if (amount === null) {
			toast.error('Informe um valor válido maior que zero');
			return;
		}
		addingWithdraw = true;
		try {
			await createWithdraw({
				fiscal_mes: selectedMonth,
				amount_brl: amount,
				withdraw_date: addWithdrawDate,
				notes: addWithdrawNotes.trim() || null
			});
			resetAddWithdrawForm();
			toast.success('Saque adicionado');
			await loadWithdraws(selectedMonth);
			await loadFluxo(selectedMonth);
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao adicionar saque'
			);
		} finally {
			addingWithdraw = false;
		}
	}

	function openEditWithdraw(item: WithdrawEntry) {
		editingWithdraw = item;
		editWithdrawDate = item.withdraw_date?.match(/^\d{4}-\d{2}-\d{2}$/)
			? item.withdraw_date
			: getTodayIsoDate();
		editWithdrawAmount = String(item.amount_brl);
		editWithdrawNotes = item.notes ?? '';
		editDialogOpen = true;
	}

	async function handleSaveWithdraw(event: SubmitEvent) {
		event.preventDefault();
		if (!editingWithdraw || !selectedMonth) return;
		const amount = parseAmountInput(editWithdrawAmount);
		if (amount === null) {
			toast.error('Informe um valor válido maior que zero');
			return;
		}
		savingWithdraw = true;
		try {
			await updateWithdraw(editingWithdraw.id, {
				amount_brl: amount,
				withdraw_date: editWithdrawDate || null,
				notes: editWithdrawNotes.trim() || null
			});
			editDialogOpen = false;
			editingWithdraw = null;
			await loadWithdraws(selectedMonth);
			await loadFluxo(selectedMonth);
			toast.success('Saque atualizado');
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao atualizar saque'
			);
		} finally {
			savingWithdraw = false;
		}
	}

	async function handleDeleteWithdraw() {
		if (!deletingWithdraw || !selectedMonth) return;
		await deleteWithdraw(deletingWithdraw.id);
		deletingWithdraw = null;
		await loadWithdraws(selectedMonth);
		await loadFluxo(selectedMonth);
		toast.success('Saque excluído');
	}

	async function handleDownloadPack() {
		if (!selectedMonth || downloadingPack) return;
		downloadingPack = true;
		try {
			const { blob, filename } = await downloadFiscalMonthPack(selectedMonth);
			triggerDownload(blob, filename ?? `documents_pj_${selectedMonth}.zip`);
			toast.success('Download iniciado');
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao baixar documentos'
			);
		} finally {
			downloadingPack = false;
		}
	}

	const activeSummary = $derived(withdrawSummary ?? emptyWithdrawSummary());
	const targetBrl = $derived(activeSummary.target_brl);

	const pctOfTarget = (value: number) =>
		Math.min(100, Math.max(0, (value / targetBrl) * 100));

	const casaNeedPct = $derived(
		fluxo ? pctOfTarget(fluxo.coverage.primary_share_brl) : 0
	);
	const saquesPct = $derived(pctOfTarget(activeSummary.total_brl));
	const incomePct = $derived(pctOfTarget(activeSummary.previous_month_income_brl));

	const withdrawZone = $derived<'safe' | 'warning' | 'over'>(
		activeSummary.over_target_brl
			? 'over'
			: activeSummary.total_brl <= activeSummary.previous_month_income_brl
				? 'safe'
				: 'warning'
	);

	const withdrawProgressFillClass = $derived(
		withdrawZone === 'over'
			? 'bg-red-500'
			: withdrawZone === 'safe'
				? 'bg-emerald-600'
				: 'bg-amber-500'
	);

	const coverageHero = $derived.by(() => {
		if (!fluxo) return null;
		const { coverage } = fluxo;
		if (coverage.covers_household) {
			return {
				text: `Cobre, sobram ${formatBrl(coverage.surplus_brl)}`,
				class: 'text-emerald-400'
			};
		}
		return {
			text: `Faltam ${formatBrl(coverage.shortfall_brl)}`,
			class: 'text-amber-400'
		};
	});

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
		fluxo?.completeness
			? [
					{
						label: 'Notas Fiscais',
						icon: FileText,
						count: fluxo.completeness.nfs_count,
						ok: fluxo.completeness.nfs_ok,
						required: 2,
						href: `/nfs?fiscal_mes=${selectedMonth}`
					},
					{
						label: 'Boletos c/ Recibo',
						icon: Receipt,
						count: fluxo.completeness.boletos_with_receipt_count,
						ok: fluxo.completeness.boletos_ok,
						required: 1,
						href: `/boletos?fiscal_mes=${selectedMonth}`
					},
					{
						label: 'DARFs c/ Recibo',
						icon: Landmark,
						count: fluxo.completeness.darfs_with_receipt_count,
						ok: fluxo.completeness.darfs_ok,
						required: 1,
						href: `/darfs?fiscal_mes=${selectedMonth}`
					},
					...(fluxo.completeness.irpj_csll_required
						? [
								{
									label: 'IRPJ/CSLL c/ Recibo',
									icon: Landmark,
									count: fluxo.completeness.irpj_csll_with_receipt_count,
									ok: fluxo.completeness.irpj_csll_ok,
									required: 1,
									href: `/irpj-csll?fiscal_mes=${selectedMonth}`
								}
							]
						: []),
					{
						label: 'Extratos c/ Caixinha',
						icon: WalletCards,
						count: fluxo.completeness.extratos_caixinha_count,
						ok: fluxo.completeness.extratos_ok,
						required: 1,
						href: `/extratos?fiscal_mes=${selectedMonth}`
					},
					{
						label: 'Higlobe',
						icon: DollarSign,
						count: fluxo.completeness.extratos_higlobe_count,
						ok: fluxo.completeness.higlobe_ok,
						required: 1,
						href: `/extratos?fiscal_mes=${selectedMonth}`,
						optional: true
					}
				]
			: []
	);
</script>

<div class="space-y-6">
	<PageHeader
		title="Fluxo"
		description="Saques cobrem o que você gastou na casa? O que sobra na empresa?"
	>
		{#snippet actions()}
			<Button
				onclick={() => {
					createMonthValue = selectedMonth || getCurrentMonthValue();
					createDialogOpen = true;
				}}
			>
				<Plus class="h-4 w-4" />
				Criar mês fiscal
			</Button>
		{/snippet}
	</PageHeader>

	<div class="flex flex-wrap items-center gap-3">
		<label for="fluxo-month" class="text-sm font-medium text-muted-foreground">Mês</label>
		{#if loading}
			<div class="h-9 w-40 animate-pulse rounded-md bg-muted"></div>
		{:else if months.length > 0}
			<select
				id="fluxo-month"
				class="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
				bind:value={selectedMonth}
			>
				{#each months as m}
					<option value={m}>{formatFiscalMes(m)}</option>
				{/each}
			</select>
			<Button
				variant="outline"
				size="sm"
				onclick={handleDownloadPack}
				disabled={!selectedMonth || downloadingPack}
			>
				<Download class="h-4 w-4" />
				{downloadingPack ? 'Baixando…' : 'Baixar documentos'}
			</Button>
		{:else}
			<span class="text-sm text-muted-foreground">Nenhum mês fiscal</span>
		{/if}

		{#if fluxo}
			<Badge variant={fluxo.casa.saved ? 'default' : 'outline'}>
				Casa: {fluxo.casa.saved ? 'salva' : 'em aberto'}
			</Badge>
			<Badge
				variant={fluxo.completeness.month_complete ? 'default' : 'outline'}
				class={fluxo.completeness.month_complete ? '' : 'border-amber-500/50 text-amber-400'}
			>
				Documentos:
				{fluxo.completeness.month_complete
					? 'completo'
					: `faltam ${fluxo.completeness_missing_count}`}
			</Badge>
		{/if}
	</div>

	{#if fluxo && selectedMonth}
		<p class="text-sm text-muted-foreground">
			O gasto da casa de {formatFiscalMes(selectedMonth)} atribuído a você é coberto com saques de
			{formatFiscalMes(selectedMonth)}, comparados à receita de
			{formatFiscalMes(fluxo.previous_fiscal_mes)}.
		</p>

		<div>
			<h2 class="mb-3 text-sm font-medium">Documentos fiscais</h2>
			<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
				{#each checks as item}
					<a href={item.href} class="block group">
						<Card.Root class="transition-colors group-hover:border-muted-foreground/30">
							<Card.Content class="flex items-center justify-between py-3">
								<div class="flex items-center gap-2">
									<item.icon class="h-4 w-4 text-muted-foreground" />
									<span class="text-sm font-medium">{item.label}</span>
								</div>
								<div class="flex items-center gap-2">
									<span class="text-sm tabular-nums">
										{item.count}/{item.required}
									</span>
									{#if item.ok}
										<CheckCircle2 class="h-4 w-4 text-emerald-400" />
									{:else}
										<AlertCircle class="h-4 w-4 text-amber-400" />
									{/if}
								</div>
							</Card.Content>
						</Card.Root>
					</a>
				{/each}
			</div>
		</div>

		{#if coverageHero}
			<div class="rounded-lg border border-border bg-card px-5 py-4">
				<p class={cn('text-2xl font-bold tabular-nums', coverageHero.class)}>
					{coverageHero.text}
				</p>
				<p class="mt-1 text-sm text-muted-foreground">
					Seu gasto {formatBrl(fluxo.coverage.primary_share_brl)} · Casa toda
					{formatBrl(fluxo.coverage.household_total_brl)} · Saques
					{formatBrl(fluxo.coverage.saques_brl)}
				</p>
			</div>
		{/if}

		<div class="space-y-2">
			<div class="relative h-3 overflow-hidden rounded-full bg-muted">
				{#if incomePct > 0}
					<div class="absolute inset-y-0 left-0 bg-emerald-500/30" style={`width: ${incomePct}%`}></div>
				{/if}
				{#if incomePct < 100}
					<div
						class="absolute inset-y-0 bg-amber-500/25"
						style={`left: ${incomePct}%; width: ${100 - incomePct}%`}
					></div>
				{/if}
				<div
					class={cn('absolute inset-y-0 left-0 rounded-full transition-all', withdrawProgressFillClass)}
					style={`width: ${saquesPct}%`}
				></div>
				{#if casaNeedPct > 0}
					<div
						class="absolute inset-y-0 w-0.5 bg-foreground/80"
						style={`left: ${casaNeedPct}%`}
						title="Seu gasto"
					></div>
				{/if}
				{#if incomePct > 0 && incomePct < 100}
					<div
						class="absolute inset-y-0 w-px bg-background/70"
						style={`left: ${incomePct}%`}
					></div>
				{/if}
			</div>
			<div class="flex flex-wrap gap-x-5 gap-y-1 text-[11px] text-muted-foreground">
				<span class="flex items-center gap-1.5">
					<span class="h-2 w-2 rounded-full bg-foreground/60"></span>
					Casa (seu gasto) {formatBrl(fluxo.coverage.primary_share_brl)}
				</span>
				<span class="flex items-center gap-1.5">
					<span class="h-2 w-2 rounded-full bg-emerald-600"></span>
					Saques {formatBrl(fluxo.coverage.saques_brl)}
				</span>
				{#if activeSummary.previous_month_income_brl > 0}
					<span class="flex items-center gap-1.5">
						<span class="h-2 w-2 rounded-full bg-emerald-500/50"></span>
						Receita {formatFiscalMes(fluxo.previous_fiscal_mes)}
						{formatBrl(activeSummary.previous_month_income_brl)}
					</span>
				{/if}
				<span class="flex items-center gap-1.5">
					<span class="h-2 w-2 rounded-full bg-amber-500/50"></span>
					Meta {formatBrl(targetBrl)}
				</span>
			</div>
		</div>

		<div class="grid gap-4 md:grid-cols-2">
			<Card.Root>
				<Card.Header class="pb-2">
					<div class="flex items-center gap-2">
						<Building2 class="h-4 w-4 text-muted-foreground" />
						<Card.Title class="text-base">Restante na empresa</Card.Title>
					</div>
				</Card.Header>
				<Card.Content class="space-y-2">
					<p class="text-2xl font-bold tabular-nums">
						{formatBrl(fluxo.company.restante_brl)}
						{#if fluxo.company.restante_estimated}
							<Badge variant="outline" class="ml-2 text-xs">estimado</Badge>
						{/if}
					</p>
					<p class="text-sm text-muted-foreground">
						NFs {formatBrl(fluxo.company.nf_income_brl)} · Impostos
						{formatBrl(fluxo.company.taxes_brl)}
						{#if fluxo.company.saldo_final_brl != null}
							· Saldo extrato {formatBrl(fluxo.company.saldo_final_brl)}
						{/if}
					</p>
					<div class="flex gap-2 pt-1">
						<a href="/extratos?fiscal_mes={selectedMonth}" class="text-sm text-chart-1 hover:underline">
							Extratos
						</a>
						<a href="/analytics" class="text-sm text-chart-1 hover:underline">Analytics</a>
					</div>
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header class="pb-2">
					<div class="flex items-center gap-2">
						<Home class="h-4 w-4 text-muted-foreground" />
						<Card.Title class="text-base">Acerto da casa</Card.Title>
					</div>
				</Card.Header>
				<Card.Content class="space-y-2">
					{#if fluxo.casa.person_names.length > 0}
						<div class="space-y-1 text-sm">
							{#each fluxo.casa.person_names as name, i}
								<div class="flex justify-between gap-4">
									<span class="text-muted-foreground">{name} no cartão</span>
									<span class="tabular-nums font-medium">
										{formatBrl(fluxo.casa.nubank_per_person[i] ?? 0)}
									</span>
								</div>
							{/each}
						</div>
					{:else}
						<p class="text-sm text-muted-foreground">Casa ainda não fechada.</p>
					{/if}
					{#each fluxo.casa.reimbursements as reimb, i}
						{#if reimb > 0}
							<div class="flex items-center gap-2 text-sm text-amber-400">
								<AlertCircle class="h-4 w-4 shrink-0" />
								{fluxo.casa.person_names[i]} deve receber {formatBrl(reimb)}
							</div>
						{/if}
					{/each}
					<a href="/casa?mes={selectedMonth}" class="text-sm text-chart-1 hover:underline">
						{fluxo.casa.saved ? 'Ver / editar casa' : `Fechar a casa de ${formatFiscalMes(selectedMonth)}`}
					</a>
				</Card.Content>
			</Card.Root>
		</div>

		<Card.Root>
			<Card.Header>
				<div class="flex items-center gap-2">
					<Banknote class="h-5 w-5 text-muted-foreground" />
					<Card.Title>Saques</Card.Title>
				</div>
				<Card.Description>
					Registre saques em BRL. A barra acima compara saques com o que você gastou na casa e a receita do
					mês anterior.
				</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-4">
				<form
					class="grid gap-3 rounded-lg border border-border p-4 sm:grid-cols-[1fr_1fr_1.5fr_auto] sm:items-end"
					novalidate
					onsubmit={handleAddWithdraw}
				>
					<div class="space-y-2">
						<label for="add-withdraw-date" class="text-sm font-medium">Data</label>
						<Input id="add-withdraw-date" type="date" bind:value={addWithdrawDate} />
					</div>
					<div class="space-y-2">
						<label for="add-withdraw-amount" class="text-sm font-medium">Valor (BRL)</label>
						<Input
							id="add-withdraw-amount"
							type="text"
							inputmode="decimal"
							placeholder="0,00"
							bind:value={addWithdrawAmount}
						/>
					</div>
					<div class="space-y-2">
						<label for="add-withdraw-notes" class="text-sm font-medium">Observações</label>
						<Input
							id="add-withdraw-notes"
							type="text"
							placeholder="Opcional"
							bind:value={addWithdrawNotes}
						/>
					</div>
					<Button type="submit" disabled={addingWithdraw}>
						<Plus class="h-4 w-4" />
						{addingWithdraw ? 'Adicionando...' : 'Adicionar saque'}
					</Button>
				</form>

				<div class="rounded-lg border border-border">
					<Table.Table>
						<Table.TableHeader>
							<Table.TableRow>
								<Table.TableHead>Data</Table.TableHead>
								<Table.TableHead class="text-right">Valor</Table.TableHead>
								<Table.TableHead>Observações</Table.TableHead>
								<Table.TableHead class="w-[100px] text-right">Ações</Table.TableHead>
							</Table.TableRow>
						</Table.TableHeader>
						<Table.TableBody>
							{#if withdrawLoading && withdrawItems.length === 0}
								<Table.TableRow>
									<Table.TableCell colspan={4} class="text-center text-muted-foreground">
										Carregando...
									</Table.TableCell>
								</Table.TableRow>
							{:else if withdrawItems.length === 0}
								<Table.TableRow>
									<Table.TableCell colspan={4} class="text-center text-muted-foreground">
										Nenhum saque. Seu gasto é {formatBrl(fluxo.coverage.primary_share_brl)}.
									</Table.TableCell>
								</Table.TableRow>
							{:else}
								{#each withdrawItems as item (item.id)}
									<Table.TableRow>
										<Table.TableCell class="tabular-nums">
											{formatWithdrawDate(item.withdraw_date)}
										</Table.TableCell>
										<Table.TableCell class="text-right tabular-nums font-medium">
											{formatBrl(item.amount_brl)}
										</Table.TableCell>
										<Table.TableCell class="text-muted-foreground">
											{item.notes?.trim() || '\u2014'}
										</Table.TableCell>
										<Table.TableCell class="text-right">
											<div class="flex justify-end gap-1">
												<Button
													variant="ghost"
													size="icon"
													class="h-8 w-8"
													onclick={() => openEditWithdraw(item)}
												>
													<Pencil class="h-4 w-4" />
												</Button>
												<Button
													variant="ghost"
													size="icon"
													class="h-8 w-8 text-destructive"
													onclick={() => {
														deletingWithdraw = item;
														deleteDialogOpen = true;
													}}
												>
													<Trash2 class="h-4 w-4" />
												</Button>
											</div>
										</Table.TableCell>
									</Table.TableRow>
								{/each}
							{/if}
						</Table.TableBody>
					</Table.Table>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	{#if !loading && months.length === 0}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<p class="text-muted-foreground">Comece criando um mês fiscal ou fechando a casa.</p>
			</Card.Content>
		</Card.Root>
	{/if}
</div>

<Dialog.Root bind:open={createDialogOpen}>
	<Dialog.Content>
		<form
			class="space-y-4"
			onsubmit={(e) => {
				e.preventDefault();
				if (!createMonthValue) return;
				creatingMonth = true;
				createFiscalMonth(createMonthValue)
					.then(() => loadMonths(createMonthValue))
					.then(() => {
						createDialogOpen = false;
						toast.success(`Mês ${formatFiscalMes(createMonthValue)} criado`);
					})
					.catch((err) =>
						toast.error(
							err instanceof ApiError ? formatApiErrorMessage(err.body) : 'Falha ao criar mês'
						)
					)
					.finally(() => (creatingMonth = false));
			}}
		>
			<Dialog.Header>
				<Dialog.Title>Criar mês fiscal</Dialog.Title>
				<Dialog.Description>Adiciona o mês à lista antes de uploads ou saques.</Dialog.Description>
			</Dialog.Header>
			<div class="space-y-2">
				<label for="create-fiscal-month" class="text-sm font-medium">Mês fiscal</label>
				<Input id="create-fiscal-month" type="month" bind:value={createMonthValue} required />
			</div>
			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (createDialogOpen = false)}>
					Cancelar
				</Button>
				<Button type="submit" disabled={creatingMonth}>
					{creatingMonth ? 'Criando...' : 'Criar'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={editDialogOpen}>
	<Dialog.Content>
		<form class="space-y-4" onsubmit={handleSaveWithdraw}>
			<Dialog.Header>
				<Dialog.Title>Editar saque</Dialog.Title>
			</Dialog.Header>
			<div class="space-y-2">
				<label for="edit-withdraw-date" class="text-sm font-medium">Data</label>
				<Input id="edit-withdraw-date" type="date" bind:value={editWithdrawDate} required />
			</div>
			<div class="space-y-2">
				<label for="edit-withdraw-amount" class="text-sm font-medium">Valor (BRL)</label>
				<Input
					id="edit-withdraw-amount"
					type="number"
					min="0.01"
					step="0.01"
					bind:value={editWithdrawAmount}
					required
				/>
			</div>
			<div class="space-y-2">
				<label for="edit-withdraw-notes" class="text-sm font-medium">Observações</label>
				<Input id="edit-withdraw-notes" type="text" bind:value={editWithdrawNotes} />
			</div>
			<Dialog.Footer>
				<Button type="button" variant="outline" onclick={() => (editDialogOpen = false)}>
					Cancelar
				</Button>
				<Button type="submit" disabled={savingWithdraw}>
					{savingWithdraw ? 'Salvando...' : 'Salvar'}
				</Button>
			</Dialog.Footer>
		</form>
	</Dialog.Content>
</Dialog.Root>

<ConfirmDialog
	bind:open={deleteDialogOpen}
	title="Excluir saque"
	description="Tem certeza? Esta ação não pode ser desfeita."
	confirmLabel="Excluir"
	onconfirm={handleDeleteWithdraw}
/>
