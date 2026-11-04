<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		formatApiErrorMessage,
		listExtratos,
		listFiscalMonths,
		deleteExtrato,
		patchExtratoFiscalMes,
		extratoParsePreview,
		createExtrato,
		getExtrato,
		updateExtratoPdf,
		updateCaixinhaPdf,
		updateHiglobePdf,
		deleteCaixinha,
		deleteHiglobe,
		downloadBlob,
		triggerDownload
	} from '$lib/api/client.js';
	import type { ExtratoEntry, ExtratoPreview } from '$lib/api/types.js';
	import { formatFiscalMes, formatBrl, formatDateBr } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import FiscalMonthPicker from '$lib/components/FiscalMonthPicker.svelte';
	import FileDropZone from '$lib/components/FileDropZone.svelte';
	import UploadActions from '$lib/components/UploadActions.svelte';
	import UploadSteps from '$lib/components/UploadSteps.svelte';
	import UploadFiles from '$lib/components/UploadFiles.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import FilePreviewDialog from '$lib/components/FilePreviewDialog.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import {
		Plus,
		Download,
		Trash2,
		Eye,
		Loader2,
		ArrowUpDown,
		CheckCircle2,
		XCircle,
		Pencil
	} from 'lucide-svelte';

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------

	let extratos = $state<ExtratoEntry[]>([]);
	let months = $state<string[]>([]);
	let loading = $state(true);
	let filterMonth = $state('');

	// Upload sheet
	let uploadOpen = $state(false);
	let uploadExtrato = $state<File | null>(null);
	let uploadCaixinha = $state<File | null>(null);
	let uploadHiglobe = $state<File | null>(null);
	let uploadPreviewing = $state(false);
	let uploadPreview = $state<ExtratoPreview | null>(null);
	let uploadFiscalMes = $state('');
	let uploadSaving = $state(false);

	// Detail sheet
	let detailOpen = $state(false);
	let detailItem = $state<ExtratoEntry | null>(null);
	let detailEntries = $state<Record<string, unknown>[]>([]);
	let detailCaixinhaEntries = $state<Record<string, unknown>[]>([]);
	let detailHiglobeEntries = $state<Record<string, unknown>[]>([]);

	// Delete
	let deleteDialogOpen = $state(false);
	let deleteTarget = $state<ExtratoEntry | null>(null);

	// File preview
	let previewOpen = $state(false);
	let previewPath = $state<string | null>(null);
	let previewTitle = $state('Visualização');
	let previewFallback = $state('file');

	// Inline fiscal month edit
	let editingFmId = $state<number | null>(null);
	let editingFmValue = $state('');

	// Sorting
	let sortField = $state<string>('period_start');
	let sortAsc = $state(false);

	// Replacement state
	let replacingExtrato = $state(false);
	let replacingCaixinha = $state(false);
	let replacingHiglobe = $state(false);
	let replaceExtratoInputEl: HTMLInputElement | undefined = $state();
	let replaceCaixinhaInputEl: HTMLInputElement | undefined = $state();
	let replaceHiglobeInputEl: HTMLInputElement | undefined = $state();

	const PRO_LABORE_VALUE = 1442.69;

	// ---------------------------------------------------------------------------
	// Lifecycle
	// ---------------------------------------------------------------------------

	onMount(async () => {
		const urlFm = $page.url.searchParams.get('fiscal_mes');
		if (urlFm) filterMonth = urlFm;

		try {
			const res = await listFiscalMonths();
			months = res.months;
		} catch {
			// non-critical
		}
		await loadExtratos();
	});

	async function loadExtratos() {
		loading = true;
		try {
			extratos = await listExtratos(filterMonth || undefined);
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar extratos'
			);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void filterMonth;
		loadExtratos();
	});

	// ---------------------------------------------------------------------------
	// Sorting
	// ---------------------------------------------------------------------------

	function toggleSort(field: string) {
		if (sortField === field) sortAsc = !sortAsc;
		else {
			sortField = field;
			sortAsc = true;
		}
	}

	const sortedExtratos = $derived(() => {
		const arr = [...extratos];
		arr.sort((a, b) => {
			const av = (a as Record<string, unknown>)[sortField];
			const bv = (b as Record<string, unknown>)[sortField];
			const aStr = av == null ? '' : String(av);
			const bStr = bv == null ? '' : String(bv);
			const cmp = aStr.localeCompare(bStr, undefined, { numeric: true });
			return sortAsc ? cmp : -cmp;
		});
		return arr;
	});

	// ---------------------------------------------------------------------------
	// Upload
	// ---------------------------------------------------------------------------

	let uploadRevision = 0;

	function invalidateUpload() {
		uploadRevision += 1;
		uploadPreview = null;
	}

	function resetUpload() {
		invalidateUpload();
		uploadExtrato = null;
		uploadCaixinha = null;
		uploadHiglobe = null;
		uploadPreviewing = false;
		uploadPreview = null;
		uploadFiscalMes = '';
		uploadSaving = false;
	}

	function openUpload() {
		resetUpload();
		uploadFiscalMes = filterMonth;
		uploadOpen = true;
	}

	function hasExpectedProLabore(entries: Record<string, unknown>[]): boolean {
		return entries.some((entry) => {
			const value = entry.valor;
			return typeof value === 'number' && Math.abs(value - PRO_LABORE_VALUE) < 0.005;
		});
	}

	function hasExpectedProLaboreFromJson(json: string | null): boolean {
		return hasExpectedProLabore(parseJsonField(json));
	}

	function warnIfProLaboreMissing(entries: Record<string, unknown>[]): void {
		if (hasExpectedProLabore(entries)) return;
		toast.warning('Pró-labore de R$ 1.442,69 não encontrado neste extrato');
	}

	async function handlePreview() {
		if (uploadPreviewing || uploadSaving) return;
		const revision = uploadRevision;
		if (!uploadExtrato) {
			toast.error('Selecione o PDF do extrato');
			return;
		}
		uploadPreview = null;
		uploadPreviewing = true;
		try {
			const preview = await extratoParsePreview(
				uploadExtrato,
				uploadCaixinha ?? undefined,
				uploadHiglobe ?? undefined
			);
			if (revision !== uploadRevision) return;
			uploadPreview = preview;
			warnIfProLaboreMissing(preview.extrato.entries);
		} catch (e) {
			if (revision !== uploadRevision) return;
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao processar o documento'
			);
		} finally {
			if (revision === uploadRevision) uploadPreviewing = false;
		}
	}

	async function handleSave() {
		if (!uploadPreview || uploadPreviewing || uploadSaving) return;
		if (!uploadExtrato || !uploadFiscalMes) {
			toast.error('Selecione o extrato e o mês fiscal');
			return;
		}
		if (uploadPreview) {
			warnIfProLaboreMissing(uploadPreview.extrato.entries);
		}
		uploadSaving = true;
		try {
			await createExtrato(
				uploadExtrato,
				uploadFiscalMes,
				uploadCaixinha ?? undefined,
				uploadHiglobe ?? undefined
			);
			toast.success('Extrato salvo');
			uploadOpen = false;
			resetUpload();
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao salvar');
		} finally {
			uploadSaving = false;
		}
	}

	// ---------------------------------------------------------------------------
	// Detail
	// ---------------------------------------------------------------------------

	function parseJsonField(json: string | null): Record<string, unknown>[] {
		if (!json) return [];
		try {
			return JSON.parse(json) as Record<string, unknown>[];
		} catch {
			return [];
		}
	}

	async function openDetail(item: ExtratoEntry) {
		detailItem = item;
		detailEntries = parseJsonField(item.extrato_entries_json);
		detailCaixinhaEntries = parseJsonField(item.caixinha_entries_json);
		detailHiglobeEntries = parseJsonField(item.higlobe_entries_json);
		replacingExtrato = false;
		replacingCaixinha = false;
		replacingHiglobe = false;
		detailOpen = true;
	}

	async function refreshDetail(id: number) {
		try {
			const fresh = await getExtrato(id);
			detailItem = fresh;
			detailEntries = parseJsonField(fresh.extrato_entries_json);
			detailCaixinhaEntries = parseJsonField(fresh.caixinha_entries_json);
			detailHiglobeEntries = parseJsonField(fresh.higlobe_entries_json);
		} catch {
			// silently fail
		}
	}

	async function downloadFile(path: string, fallbackName: string) {
		try {
			const { blob, filename } = await downloadBlob(path);
			triggerDownload(blob, filename ?? fallbackName);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao baixar');
		}
	}

	function openPreview(path: string, title: string, fallbackFilename: string) {
		previewPath = path;
		previewTitle = title;
		previewFallback = fallbackFilename;
		previewOpen = true;
	}

	// ---------------------------------------------------------------------------
	// Detail: Replace/Add PDFs
	// ---------------------------------------------------------------------------

	async function handleReplaceExtrato(files: File[]) {
		if (!detailItem || files.length === 0) return;
		replacingExtrato = true;
		try {
			const updated = await updateExtratoPdf(detailItem.id, files[0]);
			toast.success('PDF do extrato substituído');
			warnIfProLaboreMissing(parseJsonField(updated.extrato_entries_json));
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao substituir');
		} finally {
			replacingExtrato = false;
		}
	}

	async function handleReplaceCaixinha(files: File[]) {
		if (!detailItem || files.length === 0) return;
		replacingCaixinha = true;
		try {
			await updateCaixinhaPdf(detailItem.id, files[0]);
			toast.success('PDF da caixinha atualizado');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao enviar');
		} finally {
			replacingCaixinha = false;
		}
	}

	async function handleReplaceHiglobe(files: File[]) {
		if (!detailItem || files.length === 0) return;
		replacingHiglobe = true;
		try {
			await updateHiglobePdf(detailItem.id, files[0]);
			toast.success('PDF Higlobe atualizado');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao enviar');
		} finally {
			replacingHiglobe = false;
		}
	}

	async function handleRemoveCaixinha() {
		if (!detailItem) return;
		try {
			await deleteCaixinha(detailItem.id);
			toast.success('Caixinha removida');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao remover');
		}
	}

	async function handleRemoveHiglobe() {
		if (!detailItem) return;
		try {
			await deleteHiglobe(detailItem.id);
			toast.success('Higlobe removido');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao remover');
		}
	}

	function openReplaceExtratoPicker() {
		replaceExtratoInputEl?.click();
	}

	function openReplaceCaixinhaPicker() {
		replaceCaixinhaInputEl?.click();
	}

	function openReplaceHiglobePicker() {
		replaceHiglobeInputEl?.click();
	}

	function handleReplaceExtratoInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		void handleReplaceExtrato(Array.from(target.files ?? []));
		target.value = '';
	}

	function handleReplaceCaixinhaInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		void handleReplaceCaixinha(Array.from(target.files ?? []));
		target.value = '';
	}

	function handleReplaceHiglobeInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		void handleReplaceHiglobe(Array.from(target.files ?? []));
		target.value = '';
	}

	// ---------------------------------------------------------------------------
	// Inline fiscal month edit
	// ---------------------------------------------------------------------------

	function startEditFm(item: ExtratoEntry) {
		editingFmId = item.id;
		editingFmValue = item.fiscal_mes ?? '';
	}

	async function saveFm(id: number) {
		try {
			await patchExtratoFiscalMes(id, editingFmValue || null);
			toast.success('Mês fiscal atualizado');
			editingFmId = null;
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao atualizar');
		}
	}

	// ---------------------------------------------------------------------------
	// Delete
	// ---------------------------------------------------------------------------

	function confirmDelete(item: ExtratoEntry) {
		deleteTarget = item;
		deleteDialogOpen = true;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		try {
			await deleteExtrato(deleteTarget.id);
			toast.success('Extrato excluído');
			deleteTarget = null;
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao excluir');
		}
	}
</script>

<div class="space-y-6">
	<PageHeader title="Extratos" description="Extratos bancários e seus anexos.">
		{#snippet actions()}
			<Button onclick={openUpload}>
				<Plus class="h-4 w-4" />
				Enviar extrato
			</Button>
		{/snippet}
	</PageHeader>

	<!-- Filter -->
	<div class="flex flex-wrap items-end gap-3">
		<div class="space-y-1">
			<span class="text-xs font-medium text-muted-foreground">Mês fiscal</span>
			<FiscalMonthPicker bind:value={filterMonth} {months} />
		</div>
	</div>

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
		</div>
	{:else if extratos.length === 0}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<p class="text-muted-foreground">Nenhum extrato encontrado.</p>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="rounded-lg border">
			<Table.Table>
				<Table.TableHeader>
					<Table.TableRow>
						{#each [
							{ key: 'period_start', label: 'Período' },
							{ key: 'saldo_final', label: 'Saldo Final' },
							{ key: 'pro_labore', label: 'Pro-Labore' },
							{ key: 'caixinha_pdf_path', label: 'Caixinha' },
							{ key: 'higlobe_pdf_path', label: 'Higlobe' },
							{ key: 'fiscal_mes', label: 'Mês fiscal' }
						] as col}
							<Table.TableHead>
								<button
									class="flex items-center gap-1 hover:text-foreground transition-colors"
									onclick={() => toggleSort(col.key)}
								>
									{col.label}
									<ArrowUpDown class="h-3 w-3" />
								</button>
							</Table.TableHead>
						{/each}
						<Table.TableHead class="w-[100px]">Ações</Table.TableHead>
					</Table.TableRow>
				</Table.TableHeader>
				<Table.TableBody>
					{#each sortedExtratos() as item (item.id)}
						<Table.TableRow>
							<Table.TableCell class="tabular-nums">
								{formatDateBr(item.period_start)} - {formatDateBr(item.period_end)}
							</Table.TableCell>
							<Table.TableCell class="tabular-nums">{formatBrl(item.saldo_final)}</Table.TableCell>
							<Table.TableCell>
								<StatusBadge
									status={hasExpectedProLaboreFromJson(item.extrato_entries_json) ? 'success' : 'warning'}
									label={hasExpectedProLaboreFromJson(item.extrato_entries_json) ? 'Encontrado' : 'Não encontrado'}
								/>
							</Table.TableCell>
							<Table.TableCell>
								<StatusBadge
									status={item.caixinha_pdf_path ? 'success' : 'neutral'}
									label={item.caixinha_pdf_path ? 'Sim' : 'Não'}
								/>
							</Table.TableCell>
							<Table.TableCell>
								<StatusBadge
									status={item.higlobe_pdf_path ? 'success' : 'neutral'}
									label={item.higlobe_pdf_path ? 'Sim' : 'Não'}
								/>
							</Table.TableCell>
							<Table.TableCell>
								{#if editingFmId === item.id}
									<div class="flex items-center gap-1">
										<Input
											type="text"
											bind:value={editingFmValue}
											placeholder="YYYY-MM"
											class="h-7 w-24 text-xs"
											onkeydown={(e: KeyboardEvent) => {
												if (e.key === 'Enter') saveFm(item.id);
												if (e.key === 'Escape') editingFmId = null;
											}}
										/>
										<Button variant="ghost" size="sm" class="h-7 px-2 text-xs" onclick={() => saveFm(item.id)}>
											OK
										</Button>
									</div>
								{:else}
									<button
										class="text-sm hover:underline"
										onclick={() => startEditFm(item)}
									>
										{formatFiscalMes(item.fiscal_mes)}
									</button>
								{/if}
							</Table.TableCell>
							<Table.TableCell>
								<div class="flex items-center gap-1">
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => openDetail(item)} title="Visualizar">
										<Eye class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => downloadFile(`/extratos/${item.id}/extrato-pdf`, `extrato_${item.id}.pdf`)} title="Baixar">
										<Download class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7 text-destructive-foreground" onclick={() => confirmDelete(item)} title="Excluir">
										<Trash2 class="h-3.5 w-3.5" />
									</Button>
								</div>
							</Table.TableCell>
						</Table.TableRow>
					{/each}
				</Table.TableBody>
			</Table.Table>
		</div>
	{/if}
</div>

<!-- Upload Sheet -->
<Sheet.Sheet bind:open={uploadOpen} onOpenChange={(o) => { if (!o) resetUpload(); }}>
	<Sheet.SheetContent side="right">
		<Sheet.SheetHeader>
			<Sheet.SheetTitle>Enviar extrato</Sheet.SheetTitle>
			<Sheet.SheetDescription>Selecione os arquivos, processe e revise os dados antes de salvar.</Sheet.SheetDescription>
			<UploadSteps ready={!!uploadPreview} />
		</Sheet.SheetHeader>
		<div class="min-h-0 flex-1 overflow-y-auto px-6 py-4 space-y-6">
			<UploadFiles ready={!!uploadPreview} count={[uploadExtrato, uploadCaixinha, uploadHiglobe].filter(Boolean).length}>
				<!-- Three file zones -->
				<div class="space-y-2">
					<span class="text-sm font-medium">PDF do extrato <span class="text-destructive-foreground">*</span></span>
					<FileDropZone
						accept=".pdf,application/pdf"
						bind:file={uploadExtrato}
						loading={uploadPreviewing || uploadSaving}
						onchange={invalidateUpload}
						label="Arraste o extrato ou clique para escolher"
					/>
				</div>
				<div class="space-y-2">
					<span class="text-sm font-medium">PDF da caixinha (opcional)</span>
					<FileDropZone
						accept=".pdf,application/pdf"
						bind:file={uploadCaixinha}
						loading={uploadPreviewing || uploadSaving}
						onchange={invalidateUpload}
						label="Arraste a caixinha ou clique para escolher"
					/>
				</div>
				<div class="space-y-2">
					<span class="text-sm font-medium">PDF Higlobe (opcional)</span>
					<FileDropZone
						accept=".pdf,application/pdf"
						bind:file={uploadHiglobe}
						loading={uploadPreviewing || uploadSaving}
						onchange={invalidateUpload}
						label="Arraste o Higlobe ou clique para escolher"
					/>
				</div>
			</UploadFiles>

			<!-- Preview -->
			{#if uploadPreview}
				<Tabs.Tabs value="extrato">
					<Tabs.TabsList class="w-full">
						<Tabs.TabsTrigger value="extrato" class="flex-1">Extrato</Tabs.TabsTrigger>
						<Tabs.TabsTrigger value="caixinha" class="flex-1" disabled={!uploadPreview.caixinha}>Caixinha</Tabs.TabsTrigger>
						<Tabs.TabsTrigger value="higlobe" class="flex-1" disabled={!uploadPreview.higlobe}>Higlobe</Tabs.TabsTrigger>
					</Tabs.TabsList>

					<Tabs.TabsContent value="extrato">
						<Card.Root>
							<Card.Content class="pt-4">
								<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
									<dt class="text-muted-foreground">Período</dt>
									<dd>{uploadPreview.extrato.period_start} - {uploadPreview.extrato.period_end}</dd>
									<dt class="text-muted-foreground">Saldo Inicial</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.saldo_inicial)}</dd>
									<dt class="text-muted-foreground">Rendimento</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.rendimento)}</dd>
									<dt class="text-muted-foreground">Total de entradas</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.total_entradas)}</dd>
									<dt class="text-muted-foreground">Total de saídas</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.total_saidas)}</dd>
									<dt class="text-muted-foreground">Saldo Final</dt>
									<dd class="tabular-nums font-medium">{formatBrl(uploadPreview.extrato.saldo_final)}</dd>
								</dl>
								{#if uploadPreview.extrato.entries.length > 0}
									<p class="mt-3 text-xs text-muted-foreground">{uploadPreview.extrato.entries.length} movimentações extraídas</p>
								{/if}
							</Card.Content>
						</Card.Root>
					</Tabs.TabsContent>

					<Tabs.TabsContent value="caixinha">
						{#if uploadPreview.caixinha}
							<Card.Root>
								<Card.Content class="pt-4">
									<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
										<dt class="text-muted-foreground">Período</dt>
										<dd>{uploadPreview.caixinha.period_start} - {uploadPreview.caixinha.period_end}</dd>
										<dt class="text-muted-foreground">Saldo Final</dt>
										<dd class="tabular-nums font-medium">{formatBrl(uploadPreview.caixinha.saldo_final)}</dd>
									</dl>
									{#if uploadPreview.caixinha.entries.length > 0}
										<p class="mt-3 text-xs text-muted-foreground">{uploadPreview.caixinha.entries.length} movimentações extraídas</p>
									{/if}
								</Card.Content>
							</Card.Root>
						{/if}
					</Tabs.TabsContent>

					<Tabs.TabsContent value="higlobe">
						{#if uploadPreview.higlobe}
							<Card.Root>
								<Card.Content class="pt-4">
									<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
										<dt class="text-muted-foreground">Período</dt>
										<dd>{uploadPreview.higlobe.period_start} - {uploadPreview.higlobe.period_end}</dd>
									</dl>
									{#if uploadPreview.higlobe.entries.length > 0}
										<p class="mt-3 text-xs text-muted-foreground">{uploadPreview.higlobe.entries.length} movimentações extraídas</p>
									{/if}
								</Card.Content>
							</Card.Root>
						{/if}
					</Tabs.TabsContent>
				</Tabs.Tabs>

				<!-- Fiscal month -->
				<div class="space-y-2">
					<span class="text-sm font-medium">Mês fiscal <span class="text-destructive-foreground">*</span></span>
					<FiscalMonthPicker bind:value={uploadFiscalMes} {months} />
				</div>
			{/if}
		</div>

		<UploadActions
			ready={!!uploadPreview}
			processing={uploadPreviewing}
			saving={uploadSaving}
			canProcess={!!uploadExtrato}
			canSave={!!uploadFiscalMes}
			onprocess={handlePreview}
			onsave={handleSave}
			oncancel={() => { uploadOpen = false; resetUpload(); }}
		/>

	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- Detail Sheet -->
<Sheet.Sheet bind:open={detailOpen}>
	<Sheet.SheetContent side="right" class="sm:max-w-2xl">
		<Sheet.SheetHeader>
			<Sheet.SheetTitle>Detalhes do extrato</Sheet.SheetTitle>
			{#if detailItem}
				<Sheet.SheetDescription>ID: {detailItem.id} &middot; {formatFiscalMes(detailItem.fiscal_mes)}</Sheet.SheetDescription>
			{/if}
		</Sheet.SheetHeader>
		{#if detailItem}
			<div class="flex-1 overflow-y-auto px-6 py-4 space-y-5">
				<!-- Extrato PDF Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<CheckCircle2 class="h-4 w-4 text-muted-foreground" />
								<Card.Title class="text-sm">PDF do extrato</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title="Substituir PDF do extrato"
									onclick={openReplaceExtratoPicker}
									disabled={replacingExtrato}
								>
									{#if replacingExtrato}
										<Loader2 class="h-3.5 w-3.5 animate-spin" />
									{:else}
										<Pencil class="h-3.5 w-3.5" />
									{/if}
								</Button>
							</div>
							<div class="flex items-center gap-1">
								<Button
									variant="outline"
									size="sm"
									class="h-7 text-xs"
									onclick={() =>
										openPreview(
											`/extratos/${detailItem!.id}/extrato-pdf`,
											`Extrato #${detailItem!.id}`,
											`extrato_${detailItem!.id}.pdf`
										)}
									title="Ver PDF"
								>
									<Eye class="h-3.5 w-3.5" />
									Visualizar
								</Button>
								<Button
									variant="outline"
									size="sm"
									class="h-7 text-xs"
									onclick={() => downloadFile(`/extratos/${detailItem!.id}/extrato-pdf`, `extrato_${detailItem!.id}.pdf`)}
									title="Baixar PDF"
								>
									<Download class="h-3.5 w-3.5" />
									PDF
								</Button>
							</div>
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Período</dt>
							<dd class="tabular-nums">{formatDateBr(detailItem.period_start)} - {formatDateBr(detailItem.period_end)}</dd>
							<dt class="text-muted-foreground">Saldo Inicial</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.saldo_inicial)}</dd>
							<dt class="text-muted-foreground">Rendimento</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.rendimento)}</dd>
							<dt class="text-muted-foreground">Total de entradas</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.total_entradas)}</dd>
							<dt class="text-muted-foreground">Total de saídas</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.total_saidas)}</dd>
							<dt class="text-muted-foreground">Saldo Final</dt>
							<dd class="tabular-nums font-medium">{formatBrl(detailItem.saldo_final)}</dd>
							<dt class="text-muted-foreground">Status</dt>
							<dd>Anexado</dd>
						</dl>
						<div
							class={`rounded-md border px-3 py-2 text-sm ${
								hasExpectedProLabore(detailEntries)
									? 'border-border bg-muted/30 text-muted-foreground'
									: 'border-warning/25 bg-warning/10 text-warning'
							}`}
						>
							{#if hasExpectedProLabore(detailEntries)}
								Pró-labore de R$ 1.442,69 encontrado neste extrato.
							{:else}
								Pró-labore de R$ 1.442,69 não encontrado neste extrato.
							{/if}
						</div>
						<div class="space-y-2">
							<div class="text-xs font-medium text-muted-foreground">
								Movimentações ({detailEntries.length})
							</div>
							{#if detailEntries.length > 0}
								<div class="max-h-64 overflow-auto rounded-md border">
									<table class="w-full text-xs">
										<thead class="bg-muted sticky top-0">
											<tr>
												{#each Object.keys(detailEntries[0] ?? {}) as key}
													<th class="px-2 py-1 text-left font-medium text-muted-foreground">{key}</th>
												{/each}
											</tr>
										</thead>
										<tbody>
											{#each detailEntries as row}
												<tr class="border-t border-border">
													{#each Object.values(row) as val}
														<td class="px-2 py-1 whitespace-nowrap">{val ?? ''}</td>
													{/each}
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{:else}
								<p class="text-sm text-muted-foreground">Nenhuma movimentação extraída deste extrato.</p>
							{/if}
						</div>
					</Card.Content>
					<input
						bind:this={replaceExtratoInputEl}
						type="file"
						accept=".pdf,application/pdf"
						class="sr-only"
						onchange={handleReplaceExtratoInputChange}
					/>
				</Card.Root>

				<!-- Caixinha PDF Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								{#if detailItem.caixinha_pdf_path}
									<CheckCircle2 class="h-4 w-4 text-muted-foreground" />
								{:else}
									<XCircle class="h-4 w-4 text-muted-foreground" />
								{/if}
								<Card.Title class="text-sm">PDF da caixinha</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title={detailItem.caixinha_pdf_path ? 'Substituir PDF da caixinha' : 'Adicionar PDF da caixinha'}
									onclick={openReplaceCaixinhaPicker}
									disabled={replacingCaixinha}
								>
									{#if replacingCaixinha}
										<Loader2 class="h-3.5 w-3.5 animate-spin" />
									{:else}
										<Pencil class="h-3.5 w-3.5" />
									{/if}
								</Button>
							</div>
							<div class="flex items-center gap-1">
								{#if detailItem.caixinha_pdf_path}
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() =>
											openPreview(
												`/extratos/${detailItem!.id}/caixinha-pdf`,
												`Caixinha #${detailItem!.id}`,
												`caixinha_${detailItem!.id}.pdf`
											)}
										title="Ver PDF"
									>
										<Eye class="h-3.5 w-3.5" />
										Visualizar
									</Button>
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() => downloadFile(`/extratos/${detailItem!.id}/caixinha-pdf`, `caixinha_${detailItem!.id}.pdf`)}
										title="Baixar PDF"
									>
										<Download class="h-3.5 w-3.5" />
										PDF
									</Button>
									<Button
										variant="ghost"
										size="sm"
										class="h-7 text-xs text-destructive-foreground"
										onclick={handleRemoveCaixinha}
									>
										<Trash2 class="h-3.5 w-3.5" />
									</Button>
								{/if}
							</div>
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Tipo</dt>
							<dd>Anexo opcional</dd>
							<dt class="text-muted-foreground">Status</dt>
							<dd>{detailItem.caixinha_pdf_path ? 'Anexado' : 'Não anexado'}</dd>
							<dt class="text-muted-foreground">Saldo Final</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.caixinha_saldo_final)}</dd>
						</dl>
						<div class="space-y-2">
							<div class="text-xs font-medium text-muted-foreground">
								Movimentações ({detailCaixinhaEntries.length})
							</div>
							{#if detailCaixinhaEntries.length > 0}
								<div class="max-h-64 overflow-auto rounded-md border">
									<table class="w-full text-xs">
										<thead class="bg-muted sticky top-0">
											<tr>
												{#each Object.keys(detailCaixinhaEntries[0] ?? {}) as key}
													<th class="px-2 py-1 text-left font-medium text-muted-foreground">{key}</th>
												{/each}
											</tr>
										</thead>
										<tbody>
											{#each detailCaixinhaEntries as row}
												<tr class="border-t border-border">
													{#each Object.values(row) as val}
														<td class="px-2 py-1 whitespace-nowrap">{val ?? ''}</td>
													{/each}
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{:else if detailItem.caixinha_pdf_path}
								<p class="text-sm text-muted-foreground">Nenhuma movimentação extraída da caixinha.</p>
							{:else}
								<p class="text-sm text-muted-foreground">Nenhum PDF da caixinha anexado.</p>
							{/if}
						</div>
					</Card.Content>
					<input
						bind:this={replaceCaixinhaInputEl}
						type="file"
						accept=".pdf,application/pdf"
						class="sr-only"
						onchange={handleReplaceCaixinhaInputChange}
					/>
				</Card.Root>

				<!-- Higlobe PDF Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								{#if detailItem.higlobe_pdf_path}
									<CheckCircle2 class="h-4 w-4 text-muted-foreground" />
								{:else}
									<XCircle class="h-4 w-4 text-muted-foreground" />
								{/if}
								<Card.Title class="text-sm">PDF Higlobe</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title={detailItem.higlobe_pdf_path ? 'Substituir PDF Higlobe' : 'Adicionar PDF Higlobe'}
									onclick={openReplaceHiglobePicker}
									disabled={replacingHiglobe}
								>
									{#if replacingHiglobe}
										<Loader2 class="h-3.5 w-3.5 animate-spin" />
									{:else}
										<Pencil class="h-3.5 w-3.5" />
									{/if}
								</Button>
							</div>
							<div class="flex items-center gap-1">
								{#if detailItem.higlobe_pdf_path}
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() =>
											openPreview(
												`/extratos/${detailItem!.id}/higlobe-pdf`,
												`Higlobe #${detailItem!.id}`,
												`higlobe_${detailItem!.id}.pdf`
											)}
										title="Ver PDF"
									>
										<Eye class="h-3.5 w-3.5" />
										Visualizar
									</Button>
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() => downloadFile(`/extratos/${detailItem!.id}/higlobe-pdf`, `higlobe_${detailItem!.id}.pdf`)}
										title="Baixar PDF"
									>
										<Download class="h-3.5 w-3.5" />
										PDF
									</Button>
									<Button
										variant="ghost"
										size="sm"
										class="h-7 text-xs text-destructive-foreground"
										onclick={handleRemoveHiglobe}
									>
										<Trash2 class="h-3.5 w-3.5" />
									</Button>
								{/if}
							</div>
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Tipo</dt>
							<dd>Anexo opcional</dd>
							<dt class="text-muted-foreground">Status</dt>
							<dd>{detailItem.higlobe_pdf_path ? 'Anexado' : 'Não anexado'}</dd>
						</dl>
						<div class="space-y-2">
							<div class="text-xs font-medium text-muted-foreground">
								Movimentações ({detailHiglobeEntries.length})
							</div>
							{#if detailHiglobeEntries.length > 0}
								<div class="max-h-64 overflow-auto rounded-md border">
									<table class="w-full text-xs">
										<thead class="bg-muted sticky top-0">
											<tr>
												{#each Object.keys(detailHiglobeEntries[0] ?? {}) as key}
													<th class="px-2 py-1 text-left font-medium text-muted-foreground">{key}</th>
												{/each}
											</tr>
										</thead>
										<tbody>
											{#each detailHiglobeEntries as row}
												<tr class="border-t border-border">
													{#each Object.values(row) as val}
														<td class="px-2 py-1 whitespace-nowrap">{val ?? ''}</td>
													{/each}
												</tr>
											{/each}
										</tbody>
									</table>
								</div>
							{:else if detailItem.higlobe_pdf_path}
								<p class="text-sm text-muted-foreground">Nenhuma movimentação extraída do Higlobe.</p>
							{:else}
								<p class="text-sm text-muted-foreground">Nenhum PDF Higlobe anexado.</p>
							{/if}
						</div>
					</Card.Content>
					<input
						bind:this={replaceHiglobeInputEl}
						type="file"
						accept=".pdf,application/pdf"
						class="sr-only"
						onchange={handleReplaceHiglobeInputChange}
					/>
				</Card.Root>

			</div>
		{/if}
	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- File preview -->
<FilePreviewDialog
	bind:open={previewOpen}
	bind:path={previewPath}
	title={previewTitle}
	fallbackFilename={previewFallback}
/>

<!-- Delete confirmation -->
<ConfirmDialog
	bind:open={deleteDialogOpen}
	title="Excluir extrato"
	description="O extrato e todos os PDFs anexos serão excluídos."
	onconfirm={handleDelete}
/>
