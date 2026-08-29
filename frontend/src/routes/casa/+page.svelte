<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		computeCasaSplit,
		createCasaPerson,
		deleteCasaPerson,
		formatApiErrorMessage,
		getCasaWorkspace,
		listCasaPeople,
		listFiscalMonths,
		saveCasaMonth,
		updateCasaFixedBills
	} from '$lib/api/client.js';
	import type {
		CasaExpenseItem,
		CasaFixedBill,
		CasaPerson,
		CasaSplitPayload,
		CasaWorkspaceResponse
	} from '$lib/api/types.js';
	import { cn } from '$lib/utils.js';
	import { formatBrl, formatFiscalMes } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { AlertCircle, Plus, Trash2, Users, Save } from 'lucide-svelte';

	let months = $state<string[]>([]);
	let selectedMonth = $state('');
	let loading = $state(true);
	let saving = $state(false);
	let computing = $state(false);

	let people = $state<CasaPerson[]>([]);
	let fixedBills = $state<CasaFixedBill[]>([]);
	let otherExpenses = $state<CasaExpenseItem[]>([]);
	let nubank = $state(0);
	let pcts = $state<number[]>([]);
	let personIds = $state<string[]>([]);
	let ccReservedAmount = $state(0);
	let ccReservedPersonId = $state<string | null>(null);
	let isSaved = $state(false);
	let isDirty = $state(false);
	let split = $state<CasaSplitPayload | null>(null);

	let peopleDialogOpen = $state(false);
	let newPersonName = $state('');
	let newPersonId = $state('');

	let newFixedName = $state('');
	let newFixedValue = $state('');
	let newFixedPaidBy = $state('');

	let newExpenseDesc = $state('');
	let newExpenseAmount = $state('');
	let newExpensePaidBy = $state('');

	function parseAmount(value: string): number | null {
		let raw = value.trim();
		if (!raw) return null;
		if (raw.includes(',')) raw = raw.replace(/\./g, '').replace(',', '.');
		const n = Number.parseFloat(raw);
		return Number.isFinite(n) && n > 0 ? n : null;
	}

	function markDirty() {
		isDirty = true;
	}

	function applyWorkspace(ws: CasaWorkspaceResponse) {
		people = ws.people;
		fixedBills = [...ws.fixed_bills];
		otherExpenses = [...ws.other_expenses];
		nubank = ws.nubank;
		pcts = [...ws.pcts];
		personIds = [...ws.person_ids];
		ccReservedAmount = ws.cc_reserved_amount;
		ccReservedPersonId = ws.cc_reserved_person_id;
		isSaved = ws.saved;
		isDirty = false;
		split = ws.split;
		if (people.length > 0 && !newFixedPaidBy) newFixedPaidBy = people[0].id;
		if (people.length > 0 && !newExpensePaidBy) newExpensePaidBy = people[0].id;
	}

	async function loadMonths(preferred?: string) {
		const res = await listFiscalMonths();
		months = res.months;
		if (months.length === 0) {
			const today = new Date();
			selectedMonth = `${today.getFullYear()}-${`${today.getMonth() + 1}`.padStart(2, '0')}`;
			months = [selectedMonth];
			return;
		}
		if (preferred && months.includes(preferred)) {
			selectedMonth = preferred;
			return;
		}
		const urlMes = $page.url.searchParams.get('mes');
		if (urlMes && months.includes(urlMes)) {
			selectedMonth = urlMes;
			return;
		}
		if (!selectedMonth || !months.includes(selectedMonth)) {
			selectedMonth = months[0];
		}
	}

	async function loadWorkspace() {
		if (!selectedMonth) return;
		loading = true;
		try {
			const ws = await getCasaWorkspace(selectedMonth);
			applyWorkspace(ws);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar');
		} finally {
			loading = false;
		}
	}

	async function refreshSplit() {
		if (!selectedMonth || personIds.length === 0) return;
		computing = true;
		try {
			split = await computeCasaSplit({
				fiscal_mes: selectedMonth,
				person_ids: personIds,
				pcts,
				nubank,
				fixed_bills: fixedBills,
				other_expenses: otherExpenses,
				cc_reserved_amount: ccReservedAmount,
				cc_reserved_person_id: ccReservedPersonId
			});
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Erro no acerto');
		} finally {
			computing = false;
		}
	}

	onMount(async () => {
		try {
			await loadMonths();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao iniciar');
		} finally {
			loading = false;
		}
	});

	$effect(() => {
		if (!selectedMonth) return;
		void loadWorkspace();
	});

	$effect(() => {
		if (loading || !selectedMonth) return;
		const t = setTimeout(() => void refreshSplit(), 300);
		return () => clearTimeout(t);
	});

	function addFixedBill() {
		const name = newFixedName.trim();
		const val = parseAmount(newFixedValue);
		if (!name || val === null) {
			toast.error('Nome e valor válido obrigatórios');
			return;
		}
		fixedBills = [...fixedBills, { name, value: val, paid_by: newFixedPaidBy }];
		newFixedName = '';
		newFixedValue = '';
		markDirty();
	}

	function removeFixedBill(index: number) {
		fixedBills = fixedBills.filter((_, i) => i !== index);
		markDirty();
	}

	function addExpense() {
		const desc = newExpenseDesc.trim();
		const val = parseAmount(newExpenseAmount);
		if (val === null) {
			toast.error('Valor válido obrigatório');
			return;
		}
		otherExpenses = [
			...otherExpenses,
			{ description: desc, amount: val, paid_by: newExpensePaidBy }
		];
		newExpenseDesc = '';
		newExpenseAmount = '';
		markDirty();
	}

	function removeExpense(index: number) {
		otherExpenses = otherExpenses.filter((_, i) => i !== index);
		markDirty();
	}

	function onPctChange(index: number, raw: string) {
		const v = Number.parseInt(raw, 10);
		if (!Number.isFinite(v)) return;
		const newPcts = [...pcts];
		if (personIds.length === 2 && index === 0) {
			newPcts[0] = v / 100;
			newPcts[1] = 1 - newPcts[0];
		} else {
			newPcts[index] = v / 100;
		}
		pcts = newPcts;
		markDirty();
	}

	async function persistFixedBills() {
		try {
			await updateCasaFixedBills(fixedBills);
		} catch {
			/* optional sync */
		}
	}

	async function handleSave() {
		if (!selectedMonth) return;
		saving = true;
		try {
			await persistFixedBills();
			await saveCasaMonth(selectedMonth, {
				fiscal_mes: selectedMonth,
				person_ids: personIds,
				pcts,
				nubank,
				fixed_bills: fixedBills,
				other_expenses: otherExpenses,
				cc_reserved_amount: ccReservedAmount,
				cc_reserved_person_id: ccReservedPersonId
			});
			isSaved = true;
			isDirty = false;
			toast.success(`Casa de ${formatFiscalMes(selectedMonth)} salva`);
			await loadWorkspace();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao salvar');
		} finally {
			saving = false;
		}
	}

	async function handleAddPerson() {
		const name = newPersonName.trim();
		if (!name) return;
		try {
			await createCasaPerson(name, newPersonId.trim() || undefined);
			people = (await listCasaPeople()).items;
			newPersonName = '';
			newPersonId = '';
			toast.success('Pessoa adicionada');
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha');
		}
	}

	async function handleRemovePerson(id: string) {
		try {
			await deleteCasaPerson(id);
			people = (await listCasaPeople()).items;
			toast.success('Pessoa removida');
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Não foi possível remover');
		}
	}

	const personName = (id: string) => people.find((p) => p.id === id)?.name ?? id;
	const pctSum = $derived(pcts.reduce((a, b) => a + b, 0));
	const pctValid = $derived(Math.abs(pctSum - 1) < 0.01);
</script>

<div class="space-y-6">
	<PageHeader title="Casa" description="Contas da casa, cartão e acerto entre pessoas.">
		{#snippet actions()}
			<Button variant="outline" onclick={() => (peopleDialogOpen = true)}>
				<Users class="h-4 w-4" />
				Pessoas
			</Button>
		{/snippet}
	</PageHeader>

	<div class="flex flex-wrap items-center gap-3">
		<label for="casa-month" class="text-sm font-medium text-muted-foreground">Mês</label>
		<select
			id="casa-month"
			class="flex h-9 rounded-md border border-input bg-transparent px-3 py-1 text-sm"
			bind:value={selectedMonth}
		>
			{#each months as m}
				<option value={m}>{formatFiscalMes(m)}</option>
			{/each}
		</select>
		{#if isSaved && !isDirty}
			<Badge>Salva</Badge>
		{:else if isDirty}
			<Badge variant="outline" class="border-amber-500/50 text-amber-400">Edição em aberto</Badge>
		{:else}
			<Badge variant="outline">Em aberto</Badge>
		{/if}
	</div>

	{#if loading}
		<div class="h-40 animate-pulse rounded-lg bg-muted"></div>
	{:else}
		<div class="grid gap-6 lg:grid-cols-[1fr_320px]">
			<div class="space-y-6">
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Contas fixas</Card.Title>
						<Card.Description>Recorrentes — valores podem mudar (ex. água).</Card.Description>
					</Card.Header>
					<Card.Content class="space-y-4">
						<div class="rounded-lg border border-border">
							<Table.Table>
								<Table.TableHeader>
									<Table.TableRow>
										<Table.TableHead>Nome</Table.TableHead>
										<Table.TableHead class="text-right">Valor</Table.TableHead>
										<Table.TableHead>Pago por</Table.TableHead>
										<Table.TableHead class="w-12"></Table.TableHead>
									</Table.TableRow>
								</Table.TableHeader>
								<Table.TableBody>
									{#each fixedBills as bill, i}
										<Table.TableRow>
											<Table.TableCell>{bill.name}</Table.TableCell>
											<Table.TableCell class="text-right tabular-nums">
												{formatBrl(bill.value)}
											</Table.TableCell>
											<Table.TableCell>{personName(bill.paid_by)}</Table.TableCell>
											<Table.TableCell>
												<Button
													variant="ghost"
													size="icon"
													class="h-8 w-8"
													onclick={() => removeFixedBill(i)}
												>
													<Trash2 class="h-4 w-4" />
												</Button>
											</Table.TableCell>
										</Table.TableRow>
									{:else}
										<Table.TableRow>
											<Table.TableCell colspan={4} class="text-center text-muted-foreground">
												Nenhuma conta fixa.
											</Table.TableCell>
										</Table.TableRow>
									{/each}
								</Table.TableBody>
							</Table.Table>
						</div>
						<div class="grid gap-2 sm:grid-cols-4">
							<Input placeholder="Nome" bind:value={newFixedName} />
							<Input placeholder="Valor" bind:value={newFixedValue} inputmode="decimal" />
							<select
								class="flex h-9 rounded-md border border-input bg-transparent px-2 text-sm"
								bind:value={newFixedPaidBy}
							>
								{#each people as p}
									<option value={p.id}>{p.name}</option>
								{/each}
							</select>
							<Button variant="outline" onclick={addFixedBill}>
								<Plus class="h-4 w-4" />
								Adicionar
							</Button>
						</div>
					</Card.Content>
				</Card.Root>

				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Outras despesas</Card.Title>
						<Card.Description>Com descrição e quem pagou.</Card.Description>
					</Card.Header>
					<Card.Content class="space-y-4">
						<div class="rounded-lg border border-border">
							<Table.Table>
								<Table.TableHeader>
									<Table.TableRow>
										<Table.TableHead>Descrição</Table.TableHead>
										<Table.TableHead class="text-right">Valor</Table.TableHead>
										<Table.TableHead>Pago por</Table.TableHead>
										<Table.TableHead class="w-12"></Table.TableHead>
									</Table.TableRow>
								</Table.TableHeader>
								<Table.TableBody>
									{#each otherExpenses as exp, i}
										<Table.TableRow>
											<Table.TableCell>{exp.description || '—'}</Table.TableCell>
											<Table.TableCell class="text-right tabular-nums">
												{formatBrl(exp.amount)}
											</Table.TableCell>
											<Table.TableCell>{personName(exp.paid_by)}</Table.TableCell>
											<Table.TableCell>
												<Button
													variant="ghost"
													size="icon"
													class="h-8 w-8"
													onclick={() => removeExpense(i)}
												>
													<Trash2 class="h-4 w-4" />
												</Button>
											</Table.TableCell>
										</Table.TableRow>
									{:else}
										<Table.TableRow>
											<Table.TableCell colspan={4} class="text-center text-muted-foreground">
												Nenhuma despesa extra.
											</Table.TableCell>
										</Table.TableRow>
									{/each}
								</Table.TableBody>
							</Table.Table>
						</div>
						<div class="grid gap-2 sm:grid-cols-4">
							<Input placeholder="Descrição" bind:value={newExpenseDesc} />
							<Input placeholder="Valor" bind:value={newExpenseAmount} inputmode="decimal" />
							<select
								class="flex h-9 rounded-md border border-input bg-transparent px-2 text-sm"
								bind:value={newExpensePaidBy}
							>
								{#each people as p}
									<option value={p.id}>{p.name}</option>
								{/each}
							</select>
							<Button variant="outline" onclick={addExpense}>
								<Plus class="h-4 w-4" />
								Adicionar
							</Button>
						</div>
					</Card.Content>
				</Card.Root>

				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Cartão</Card.Title>
					</Card.Header>
					<Card.Content class="space-y-4">
						<div class="grid gap-4 sm:grid-cols-2">
							<div class="space-y-2">
								<label for="nubank" class="text-sm font-medium">Fatura total (R$)</label>
								<input
									id="nubank"
									type="number"
									min="0"
									step="100"
									class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
									value={nubank}
									oninput={(e) => {
										nubank = Number((e.currentTarget as HTMLInputElement).value) || 0;
										markDirty();
									}}
								/>
							</div>
							<div class="space-y-2">
								<label for="cc-reserved" class="text-sm font-medium">Fatia exclusiva (R$)</label>
								<input
									id="cc-reserved"
									type="number"
									min="0"
									step="50"
									class="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm"
									value={ccReservedAmount}
									oninput={(e) => {
										ccReservedAmount =
											Number((e.currentTarget as HTMLInputElement).value) || 0;
										markDirty();
									}}
								/>
							</div>
						</div>
						{#if ccReservedAmount > 0}
							<div class="space-y-2">
								<label for="cc-owner" class="text-sm font-medium">Quem paga a fatia exclusiva</label>
								<select
									id="cc-owner"
									class="flex h-9 w-full rounded-md border border-input bg-transparent px-2 text-sm"
									value={ccReservedPersonId ?? personIds[0]}
									onchange={(e) => {
										ccReservedPersonId = (e.currentTarget as HTMLSelectElement).value;
										markDirty();
									}}
								>
									{#each personIds as pid}
										<option value={pid}>{personName(pid)}</option>
									{/each}
								</select>
							</div>
						{/if}
					</Card.Content>
				</Card.Root>
			</div>

			<div class="lg:sticky lg:top-20 lg:self-start space-y-4">
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Acerto</Card.Title>
						{#if computing}
							<Card.Description>Calculando...</Card.Description>
						{/if}
					</Card.Header>
					<Card.Content class="space-y-4">
						{#if personIds.length === 2}
							<div class="space-y-2">
								<label for="pct-slider-0" class="text-sm font-medium">
									{personName(personIds[0])} %
								</label>
								<input
									id="pct-slider-0"
									type="range"
									min="0"
									max="100"
									step="5"
									value={Math.round(pcts[0] * 100)}
									class="w-full"
									oninput={(e) =>
										onPctChange(0, (e.currentTarget as HTMLInputElement).value)}
								/>
								<p class="text-xs text-muted-foreground">
									{personName(personIds[0])} {Math.round(pcts[0] * 100)}% ·
									{personName(personIds[1])} {Math.round(pcts[1] * 100)}%
								</p>
							</div>
						{:else}
							{#each personIds as pid, i}
								<div class="flex items-center gap-2">
									<span class="text-sm flex-1">{personName(pid)}</span>
									<input
										type="number"
										min="0"
										max="100"
										class="flex h-9 w-20 rounded-md border border-input bg-transparent px-2 text-sm"
										value={Math.round(pcts[i] * 100)}
										oninput={(e) =>
											onPctChange(i, (e.currentTarget as HTMLInputElement).value)}
									/>
									<span class="text-sm text-muted-foreground">%</span>
								</div>
							{/each}
							{#if !pctValid}
								<p class="text-xs text-amber-400">Percentuais devem somar 100%.</p>
							{/if}
						{/if}

						{#if split}
							<div class="space-y-2 border-t border-border pt-3">
								<p class="text-sm text-muted-foreground">
									Total {formatBrl(split.total)}
								</p>
								{#each split.person_names as name, i}
									<div class="flex justify-between text-sm">
										<span>{name} no cartão</span>
										<span class="tabular-nums font-medium">
											{formatBrl(split.nubank_per_person[i])}
										</span>
									</div>
									{#if split.reimbursements[i] > 0}
										<div class="flex items-center gap-1 text-xs text-amber-400">
											<AlertCircle class="h-3 w-3" />
											Reembolso {formatBrl(split.reimbursements[i])}
										</div>
									{/if}
								{/each}
							</div>
						{/if}

						<Button
							class="w-full"
							disabled={saving || !pctValid}
							onclick={() => void handleSave()}
						>
							<Save class="h-4 w-4" />
							{saving ? 'Salvando...' : `Salvar ${formatFiscalMes(selectedMonth)}`}
						</Button>
					</Card.Content>
				</Card.Root>
			</div>
		</div>
	{/if}
</div>

<Dialog.Root bind:open={peopleDialogOpen}>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>Pessoas</Dialog.Title>
			<Dialog.Description>Quem divide as contas da casa.</Dialog.Description>
		</Dialog.Header>
		<div class="space-y-3">
			{#each people as p}
				<div class="flex items-center justify-between gap-2">
					<div>
						<p class="font-medium">{p.name}</p>
						<p class="text-xs text-muted-foreground">{p.id}</p>
					</div>
					<Button variant="ghost" size="icon" onclick={() => void handleRemovePerson(p.id)}>
						<Trash2 class="h-4 w-4" />
					</Button>
				</div>
			{/each}
			<div class="grid gap-2 pt-2 border-t border-border">
				<Input placeholder="Nome" bind:value={newPersonName} />
				<Input placeholder="Id (opcional)" bind:value={newPersonId} />
				<Button variant="outline" onclick={() => void handleAddPerson()}>
					<Plus class="h-4 w-4" />
					Adicionar pessoa
				</Button>
			</div>
		</div>
	</Dialog.Content>
</Dialog.Root>
