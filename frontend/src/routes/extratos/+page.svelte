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
	let previewTitle = $state('Preview');
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
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load extratos'
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

	function resetUpload() {
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
		toast.warning('Pro-Labore value 1.442,69 not found in this extrato');
	}

	async function handlePreview() {
		if (!uploadExtrato) {
			toast.error('Extrato PDF is required');
			return;
		}
		uploadPreview = null;
		uploadPreviewing = true;
		try {
			uploadPreview = await extratoParsePreview(
				uploadExtrato,
				uploadCaixinha ?? undefined,
				uploadHiglobe ?? undefined
			);
			warnIfProLaboreMissing(uploadPreview.extrato.entries);
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Preview failed'
			);
		} finally {
			uploadPreviewing = false;
		}
	}

	async function handleSave() {
		if (!uploadExtrato || !uploadFiscalMes) {
			toast.error('Extrato PDF and fiscal month are required');
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
			toast.success('Extrato saved successfully');
			uploadOpen = false;
			resetUpload();
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Save failed');
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
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Download failed');
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
			toast.success('Extrato PDF replaced');
			warnIfProLaboreMissing(parseJsonField(updated.extrato_entries_json));
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Replace failed');
		} finally {
			replacingExtrato = false;
		}
	}

	async function handleReplaceCaixinha(files: File[]) {
		if (!detailItem || files.length === 0) return;
		replacingCaixinha = true;
		try {
			await updateCaixinhaPdf(detailItem.id, files[0]);
			toast.success('Caixinha PDF updated');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Upload failed');
		} finally {
			replacingCaixinha = false;
		}
	}

	async function handleReplaceHiglobe(files: File[]) {
		if (!detailItem || files.length === 0) return;
		replacingHiglobe = true;
		try {
			await updateHiglobePdf(detailItem.id, files[0]);
			toast.success('Higlobe PDF updated');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Upload failed');
		} finally {
			replacingHiglobe = false;
		}
	}

	async function handleRemoveCaixinha() {
		if (!detailItem) return;
		try {
			await deleteCaixinha(detailItem.id);
			toast.success('Caixinha removed');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Remove failed');
		}
	}

	async function handleRemoveHiglobe() {
		if (!detailItem) return;
		try {
			await deleteHiglobe(detailItem.id);
			toast.success('Higlobe removed');
			await refreshDetail(detailItem.id);
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Remove failed');
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
			toast.success('Fiscal month updated');
			editingFmId = null;
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Update failed');
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
			toast.success('Extrato deleted');
			deleteTarget = null;
			await loadExtratos();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Delete failed');
		}
	}
</script>

<div class="space-y-6">
	<PageHeader title="Extratos" description="Manage bank statements, caixinha and higlobe">
		{#snippet actions()}
			<Button onclick={openUpload}>
				<Plus class="h-4 w-4" />
				Upload Extrato
			</Button>
		{/snippet}
	</PageHeader>

	<!-- Filter -->
	<div class="flex flex-wrap items-end gap-3">
		<div class="space-y-1">
			<span class="text-xs font-medium text-muted-foreground">Fiscal Month</span>
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
				<p class="text-muted-foreground">No extratos found.</p>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="rounded-lg border">
			<Table.Table>
				<Table.TableHeader>
					<Table.TableRow>
						{#each [
							{ key: 'period_start', label: 'Period' },
							{ key: 'saldo_final', label: 'Saldo Final' },
							{ key: 'pro_labore', label: 'Pro-Labore' },
							{ key: 'caixinha_pdf_path', label: 'Caixinha' },
							{ key: 'higlobe_pdf_path', label: 'Higlobe' },
							{ key: 'fiscal_mes', label: 'Fiscal Month' }
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
						<Table.TableHead class="w-[100px]">Actions</Table.TableHead>
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
									label={hasExpectedProLaboreFromJson(item.extrato_entries_json) ? 'Found' : 'Missing'}
								/>
							</Table.TableCell>
							<Table.TableCell>
								<StatusBadge
									status={item.caixinha_pdf_path ? 'success' : 'neutral'}
									label={item.caixinha_pdf_path ? 'Yes' : 'No'}
								/>
							</Table.TableCell>
							<Table.TableCell>
								<StatusBadge
									status={item.higlobe_pdf_path ? 'success' : 'neutral'}
									label={item.higlobe_pdf_path ? 'Yes' : 'No'}
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
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => openDetail(item)} title="View">
										<Eye class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => downloadFile(`/extratos/${item.id}/extrato-pdf`, `extrato_${item.id}.pdf`)} title="Download">
										<Download class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7 text-destructive-foreground" onclick={() => confirmDelete(item)} title="Delete">
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
			<Sheet.SheetTitle>Upload Extrato</Sheet.SheetTitle>
			<Sheet.SheetDescription>Upload bank statement and optional attachments.</Sheet.SheetDescription>
		</Sheet.SheetHeader>
		<div class="flex-1 overflow-y-auto px-6 py-4 space-y-6">
			<!-- Three file zones -->
			<div class="space-y-2">
				<span class="text-sm font-medium">Extrato PDF <span class="text-destructive-foreground">*</span></span>
				<FileDropZone
					accept=".pdf,application/pdf"
					bind:file={uploadExtrato}
					label="Drop extrato PDF here"
				/>
			</div>
			<div class="space-y-2">
				<span class="text-sm font-medium">Caixinha PDF (optional)</span>
				<FileDropZone
					accept=".pdf,application/pdf"
					bind:file={uploadCaixinha}
					label="Drop caixinha PDF here"
				/>
			</div>
			<div class="space-y-2">
				<span class="text-sm font-medium">Higlobe PDF (optional)</span>
				<FileDropZone
					accept=".pdf,application/pdf"
					bind:file={uploadHiglobe}
					label="Drop higlobe PDF here"
				/>
			</div>

			{#if uploadExtrato && !uploadPreview}
				<Button onclick={handlePreview} disabled={uploadPreviewing} variant="outline" class="w-full">
					{#if uploadPreviewing}
						<Loader2 class="h-4 w-4 animate-spin" />
						Parsing...
					{:else}
						Preview
					{/if}
				</Button>
			{/if}

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
									<dt class="text-muted-foreground">Period</dt>
									<dd>{uploadPreview.extrato.period_start} - {uploadPreview.extrato.period_end}</dd>
									<dt class="text-muted-foreground">Saldo Inicial</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.saldo_inicial)}</dd>
									<dt class="text-muted-foreground">Rendimento</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.rendimento)}</dd>
									<dt class="text-muted-foreground">Total Entradas</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.total_entradas)}</dd>
									<dt class="text-muted-foreground">Total Saidas</dt>
									<dd class="tabular-nums">{formatBrl(uploadPreview.extrato.total_saidas)}</dd>
									<dt class="text-muted-foreground">Saldo Final</dt>
									<dd class="tabular-nums font-medium">{formatBrl(uploadPreview.extrato.saldo_final)}</dd>
								</dl>
								{#if uploadPreview.extrato.entries.length > 0}
									<p class="mt-3 text-xs text-muted-foreground">{uploadPreview.extrato.entries.length} entries parsed</p>
								{/if}
							</Card.Content>
						</Card.Root>
					</Tabs.TabsContent>

					<Tabs.TabsContent value="caixinha">
						{#if uploadPreview.caixinha}
							<Card.Root>
								<Card.Content class="pt-4">
									<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
										<dt class="text-muted-foreground">Period</dt>
										<dd>{uploadPreview.caixinha.period_start} - {uploadPreview.caixinha.period_end}</dd>
										<dt class="text-muted-foreground">Saldo Final</dt>
										<dd class="tabular-nums font-medium">{formatBrl(uploadPreview.caixinha.saldo_final)}</dd>
									</dl>
									{#if uploadPreview.caixinha.entries.length > 0}
										<p class="mt-3 text-xs text-muted-foreground">{uploadPreview.caixinha.entries.length} entries parsed</p>
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
										<dt class="text-muted-foreground">Period</dt>
										<dd>{uploadPreview.higlobe.period_start} - {uploadPreview.higlobe.period_end}</dd>
									</dl>
									{#if uploadPreview.higlobe.entries.length > 0}
										<p class="mt-3 text-xs text-muted-foreground">{uploadPreview.higlobe.entries.length} entries parsed</p>
									{/if}
								</Card.Content>
							</Card.Root>
						{/if}
					</Tabs.TabsContent>
				</Tabs.Tabs>

				<!-- Fiscal month -->
				<div class="space-y-2">
					<span class="text-sm font-medium">Fiscal Month <span class="text-destructive-foreground">*</span></span>
					<FiscalMonthPicker bind:value={uploadFiscalMes} {months} />
				</div>
			{/if}
		</div>

		{#if uploadPreview}
			<Sheet.SheetFooter>
				<Button
					onclick={handleSave}
					disabled={uploadSaving || !uploadFiscalMes}
					class="w-full sm:w-auto"
				>
					{#if uploadSaving}
						<Loader2 class="h-4 w-4 animate-spin" />
						Saving...
					{:else}
						Save Extrato
					{/if}
				</Button>
			</Sheet.SheetFooter>
		{/if}
	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- Detail Sheet -->
<Sheet.Sheet bind:open={detailOpen}>
	<Sheet.SheetContent side="right" class="sm:max-w-2xl">
		<Sheet.SheetHeader>
			<Sheet.SheetTitle>Extrato Details</Sheet.SheetTitle>
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
								<CheckCircle2 class="h-4 w-4 text-emerald-500" />
								<Card.Title class="text-sm">Extrato PDF</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title="Replace extrato PDF"
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
									title="View PDF"
								>
									<Eye class="h-3.5 w-3.5" />
									View
								</Button>
								<Button
									variant="outline"
									size="sm"
									class="h-7 text-xs"
									onclick={() => downloadFile(`/extratos/${detailItem!.id}/extrato-pdf`, `extrato_${detailItem!.id}.pdf`)}
									title="Download PDF"
								>
									<Download class="h-3.5 w-3.5" />
									PDF
								</Button>
							</div>
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Period</dt>
							<dd class="tabular-nums">{formatDateBr(detailItem.period_start)} - {formatDateBr(detailItem.period_end)}</dd>
							<dt class="text-muted-foreground">Saldo Inicial</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.saldo_inicial)}</dd>
							<dt class="text-muted-foreground">Rendimento</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.rendimento)}</dd>
							<dt class="text-muted-foreground">Total Entradas</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.total_entradas)}</dd>
							<dt class="text-muted-foreground">Total Saidas</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.total_saidas)}</dd>
							<dt class="text-muted-foreground">Saldo Final</dt>
							<dd class="tabular-nums font-medium">{formatBrl(detailItem.saldo_final)}</dd>
							<dt class="text-muted-foreground">Status</dt>
							<dd>Attached</dd>
						</dl>
						<div
							class={`rounded-md border px-3 py-2 text-sm ${
								hasExpectedProLabore(detailEntries)
									? 'border-emerald-500/25 bg-emerald-500/10 text-emerald-300'
									: 'border-amber-500/25 bg-amber-500/10 text-amber-300'
							}`}
						>
							{#if hasExpectedProLabore(detailEntries)}
								Pro-Labore value 1.442,69 found in this extrato.
							{:else}
								Warning: Pro-Labore value 1.442,69 was not found in this extrato.
							{/if}
						</div>
						<div class="space-y-2">
							<div class="text-xs font-medium text-muted-foreground">
								Parsed Entries ({detailEntries.length})
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
								<p class="text-sm text-muted-foreground">No parsed entries found for this extrato.</p>
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
									<CheckCircle2 class="h-4 w-4 text-emerald-500" />
								{:else}
									<XCircle class="h-4 w-4 text-muted-foreground" />
								{/if}
								<Card.Title class="text-sm">Caixinha PDF</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title={detailItem.caixinha_pdf_path ? 'Replace caixinha PDF' : 'Add caixinha PDF'}
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
										title="View PDF"
									>
										<Eye class="h-3.5 w-3.5" />
										View
									</Button>
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() => downloadFile(`/extratos/${detailItem!.id}/caixinha-pdf`, `caixinha_${detailItem!.id}.pdf`)}
										title="Download PDF"
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
							<dt class="text-muted-foreground">Type</dt>
							<dd>Optional attachment</dd>
							<dt class="text-muted-foreground">Status</dt>
							<dd>{detailItem.caixinha_pdf_path ? 'Attached' : 'Not attached'}</dd>
							<dt class="text-muted-foreground">Saldo Final</dt>
							<dd class="tabular-nums">{formatBrl(detailItem.caixinha_saldo_final)}</dd>
						</dl>
						<div class="space-y-2">
							<div class="text-xs font-medium text-muted-foreground">
								Parsed Entries ({detailCaixinhaEntries.length})
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
								<p class="text-sm text-muted-foreground">No parsed entries found for this caixinha PDF.</p>
							{:else}
								<p class="text-sm text-muted-foreground">No caixinha PDF attached.</p>
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
									<CheckCircle2 class="h-4 w-4 text-emerald-500" />
								{:else}
									<XCircle class="h-4 w-4 text-muted-foreground" />
								{/if}
								<Card.Title class="text-sm">Higlobe PDF</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title={detailItem.higlobe_pdf_path ? 'Replace Higlobe PDF' : 'Add Higlobe PDF'}
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
										title="View PDF"
									>
										<Eye class="h-3.5 w-3.5" />
										View
									</Button>
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() => downloadFile(`/extratos/${detailItem!.id}/higlobe-pdf`, `higlobe_${detailItem!.id}.pdf`)}
										title="Download PDF"
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
							<dt class="text-muted-foreground">Type</dt>
							<dd>Optional attachment</dd>
							<dt class="text-muted-foreground">Status</dt>
							<dd>{detailItem.higlobe_pdf_path ? 'Attached' : 'Not attached'}</dd>
						</dl>
						<div class="space-y-2">
							<div class="text-xs font-medium text-muted-foreground">
								Parsed Entries ({detailHiglobeEntries.length})
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
								<p class="text-sm text-muted-foreground">No parsed entries found for this Higlobe PDF.</p>
							{:else}
								<p class="text-sm text-muted-foreground">No Higlobe PDF attached.</p>
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
	title="Delete Extrato"
	description="This will permanently remove the extrato and all attached PDFs."
	onconfirm={handleDelete}
/>
