<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		createFiscalMonth,
		listFiscalMonths,
		getCompleteness,
		listWithdraws,
		createWithdraw,
		updateWithdraw,
		deleteWithdraw,
		formatApiErrorMessage
	} from '$lib/api/client.js';
	import type {
		CompletenessResponse,
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
		Banknote
	} from 'lucide-svelte';

	let months = $state<string[]>([]);
	let selectedMonth = $state('');
	let completeness = $state<CompletenessResponse | null>(null);
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

	const WITHDRAW_TARGET_BRL = 50_000;

	function emptyWithdrawSummary(): WithdrawSummary {
		return {
			target_brl: WITHDRAW_TARGET_BRL,
			total_brl: 0,
			remaining_brl: WITHDRAW_TARGET_BRL,
			over_target_brl: 0,
			target_reached: false
		};
	}

	function computeLocalSummary(items: WithdrawEntry[]): WithdrawSummary {
		const total = items.reduce((sum, item) => sum + item.amount_brl, 0);
		return {
			target_brl: WITHDRAW_TARGET_BRL,
			total_brl: Math.round(total * 100) / 100,
			remaining_brl: Math.max(0, WITHDRAW_TARGET_BRL - total),
			over_target_brl: Math.max(0, total - WITHDRAW_TARGET_BRL),
			target_reached: total >= WITHDRAW_TARGET_BRL
		};
	}

	function getTodayIsoDate(): string {
		const today = new Date();
		const month = `${today.getMonth() + 1}`.padStart(2, '0');
		const day = `${today.getDate()}`.padStart(2, '0');
		return `${today.getFullYear()}-${month}-${day}`;
	}

	function parseAmountInput(value: string | number | null | undefined): number | null {
		if (value == null) return null;
		let raw = String(value).trim();
		if (!raw) return null;
		if (raw.includes(',')) {
			raw = raw.replace(/\./g, '').replace(',', '.');
		}
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
			const msg = e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load';
			toast.error(msg);
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!selectedMonth) {
			completeness = null;
			withdrawItems = [];
			withdrawSummary = null;
			return;
		}
		addWithdrawDate = getTodayIsoDate();
		void loadCompleteness(selectedMonth);
		void loadWithdraws(selectedMonth);
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

	async function loadWithdraws(fm: string) {
		withdrawLoading = true;
		try {
			const response = await listWithdraws(fm);
			withdrawItems = response.items;
			withdrawSummary = response.summary;
		} catch (e) {
			withdrawItems = [];
			withdrawSummary = emptyWithdrawSummary();
			const msg =
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar saques';
			toast.error(msg);
		} finally {
			withdrawLoading = false;
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

	async function handleAddWithdraw(event: SubmitEvent) {
		event.preventDefault();
		if (!selectedMonth) {
			toast.error('Selecione um mês fiscal');
			return;
		}

		const form = event.currentTarget as HTMLFormElement;
		const formData = new FormData(form);
		const dateValue = String(formData.get('withdraw_date') ?? addWithdrawDate ?? '').trim();
		const amountValue = String(formData.get('amount_brl') ?? addWithdrawAmount ?? '').trim();
		const notesValue = String(formData.get('notes') ?? addWithdrawNotes ?? '').trim();

		if (!dateValue) {
			toast.error('Informe a data do saque');
			return;
		}

		const amount = parseAmountInput(amountValue);
		if (amount === null) {
			toast.error('Informe um valor válido maior que zero');
			return;
		}

		addingWithdraw = true;
		try {
			const created = await createWithdraw({
				fiscal_mes: selectedMonth,
				amount_brl: amount,
				withdraw_date: dateValue,
				notes: notesValue || null
			});
			const nextItems = [created, ...withdrawItems.filter((item) => item.id !== created.id)];
			withdrawItems = nextItems;
			withdrawSummary = computeLocalSummary(nextItems);
			resetAddWithdrawForm();
			toast.success('Saque adicionado');
			void loadWithdraws(selectedMonth);
		} catch (e) {
			const msg =
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao adicionar saque';
			toast.error(msg);
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
			toast.success('Withdrawal updated');
		} catch (e) {
			const msg =
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to update withdrawal';
			toast.error(msg);
		} finally {
			savingWithdraw = false;
		}
	}

	function openDeleteWithdraw(item: WithdrawEntry) {
		deletingWithdraw = item;
		deleteDialogOpen = true;
	}

	async function handleDeleteWithdraw() {
		if (!deletingWithdraw || !selectedMonth) return;
		await deleteWithdraw(deletingWithdraw.id);
		deletingWithdraw = null;
		await loadWithdraws(selectedMonth);
		toast.success('Withdrawal deleted');
	}

	const activeWithdrawSummary = $derived(withdrawSummary ?? emptyWithdrawSummary());

	const withdrawProgress = $derived(
		Math.min(100, (activeWithdrawSummary.total_brl / activeWithdrawSummary.target_brl) * 100)
	);

	const withdrawStatusClass = $derived(
		activeWithdrawSummary.over_target_brl
			? 'text-red-400'
			: activeWithdrawSummary.target_reached
				? 'text-emerald-400'
				: 'text-amber-400'
	);

	const withdrawStatusLabel = $derived(
		activeWithdrawSummary.over_target_brl
			? `Acima da meta: ${formatBrl(activeWithdrawSummary.over_target_brl)}`
			: activeWithdrawSummary.target_reached
				? 'Meta atingida'
				: `Faltam ${formatBrl(activeWithdrawSummary.remaining_brl)}`
	);

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

	{#if selectedMonth}
		<Card.Root>
			<Card.Header>
				<div class="flex items-center gap-2">
					<Banknote class="h-5 w-5 text-muted-foreground" />
					<Card.Title>Saques</Card.Title>
				</div>
				<Card.Description>
					Registre saques em BRL conforme ocorrem e acompanhe o progresso até a meta de
					{formatBrl(50_000)}.
				</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-6">
				<div class="grid gap-4 sm:grid-cols-3">
					<div>
						<p class="text-sm text-muted-foreground">Total sacado</p>
						<p class="text-2xl font-bold tabular-nums">
							{formatBrl(activeWithdrawSummary.total_brl)}
						</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Meta</p>
						<p class="text-2xl font-bold tabular-nums">
							{formatBrl(activeWithdrawSummary.target_brl)}
						</p>
					</div>
					<div>
						<p class="text-sm text-muted-foreground">Status</p>
						<p class={cn('text-2xl font-bold tabular-nums', withdrawStatusClass)}>
							{withdrawStatusLabel}
						</p>
					</div>
				</div>

				<div class="space-y-2">
					<div class="flex items-center justify-between text-xs text-muted-foreground">
						<span>Progresso</span>
						<span>{withdrawProgress.toFixed(0)}%</span>
					</div>
					<div class="h-2 overflow-hidden rounded-full bg-muted">
						<div
							class={cn(
								'h-full rounded-full transition-all',
								activeWithdrawSummary.over_target_brl
									? 'bg-red-500'
									: activeWithdrawSummary.target_reached
										? 'bg-emerald-500'
										: 'bg-amber-500'
							)}
							style={`width: ${withdrawProgress}%`}
						></div>
					</div>
				</div>

				<form
					class="grid gap-3 rounded-lg border border-border p-4 sm:grid-cols-[1fr_1fr_1.5fr_auto] sm:items-end"
					novalidate
					onsubmit={handleAddWithdraw}
				>
					<div class="space-y-2">
						<label for="add-withdraw-date" class="text-sm font-medium">Data</label>
						<Input
							id="add-withdraw-date"
							name="withdraw_date"
							type="date"
							bind:value={addWithdrawDate}
						/>
					</div>
					<div class="space-y-2">
						<label for="add-withdraw-amount" class="text-sm font-medium">Valor (BRL)</label>
						<Input
							id="add-withdraw-amount"
							name="amount_brl"
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
							name="notes"
							type="text"
							placeholder="Opcional"
							bind:value={addWithdrawNotes}
						/>
					</div>
					<Button type="submit" disabled={addingWithdraw || !selectedMonth}>
						<Plus class="h-4 w-4" />
						{addingWithdraw ? 'Adicionando...' : 'Adicionar saque'}
					</Button>
				</form>

				<div class="space-y-3">
					<h3 class="text-sm font-medium">Saques registrados</h3>

					{#if withdrawLoading && withdrawItems.length === 0}
						<div class="h-20 animate-pulse rounded-md bg-muted"></div>
					{:else}
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
									{#if withdrawItems.length === 0}
										<Table.TableRow>
											<Table.TableCell colspan={4} class="text-center text-muted-foreground">
												Nenhum saque registrado neste mês.
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
															title="Editar"
															onclick={() => openEditWithdraw(item)}
														>
															<Pencil class="h-4 w-4" />
														</Button>
														<Button
															variant="ghost"
															size="icon"
															class="h-8 w-8 text-destructive hover:text-destructive"
															title="Excluir"
															onclick={() => openDeleteWithdraw(item)}
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
					{/if}
				</div>
			</Card.Content>
		</Card.Root>
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

<Dialog.Root bind:open={editDialogOpen}>
	<Dialog.Content>
		<form class="space-y-4" onsubmit={handleSaveWithdraw}>
			<Dialog.Header>
				<Dialog.Title>Editar saque</Dialog.Title>
				<Dialog.Description>Atualize os dados do saque selecionado.</Dialog.Description>
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
	description="Tem certeza que deseja excluir este saque? Esta ação não pode ser desfeita."
	confirmLabel="Excluir"
	onconfirm={handleDeleteWithdraw}
/>
