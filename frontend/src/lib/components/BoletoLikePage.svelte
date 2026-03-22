<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		formatApiErrorMessage,
		listFiscalMonths,
		receiptParsePreview,
		downloadBlob,
		triggerDownload
	} from '$lib/api/client.js';
	import type {
		BoletoEntry,
		BoletoLikeFieldsPatch,
		BoletoPreview,
		ReceiptPreview
	} from '$lib/api/types.js';
	import { formatFiscalMes, formatBrl, formatDateBr } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import FiscalMonthPicker from '$lib/components/FiscalMonthPicker.svelte';
	import FileDropZone from '$lib/components/FileDropZone.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import {
		Plus,
		Download,
		Trash2,
		Eye,
		Loader2,
		ArrowUpDown,
		FileWarning,
		RefreshCw,
		FileText,
		Receipt,
		Pencil
	} from 'lucide-svelte';

	let {
		domainLabel,
		routePrefix,
		listFn,
		parsePreviewFn,
		createFn,
		deleteFn,
		patchFiscalMesFn,
		patchFieldsFn,
		getBarcodeDiffFn,
		replacePdfFn,
		replaceReceiptFn,
		getFn
	}: {
		domainLabel: string;
		routePrefix: string;
		listFn: (fiscalMes?: string) => Promise<BoletoEntry[]>;
		parsePreviewFn: (file: File) => Promise<BoletoPreview>;
		createFn: (
			file: File,
			fiscalMes: string,
			receipt?: File,
			receiptDate?: string,
			receiptTime?: string
		) => Promise<BoletoEntry>;
		deleteFn: (id: number) => Promise<void>;
		patchFiscalMesFn: (id: number, fm: string | null) => Promise<BoletoEntry>;
		patchFieldsFn: (id: number, payload: BoletoLikeFieldsPatch) => Promise<BoletoEntry>;
		getBarcodeDiffFn: (id: number) => Promise<string>;
		replacePdfFn: (id: number, file: File) => Promise<BoletoEntry>;
		replaceReceiptFn: (
			id: number,
			receipt: File,
			receiptDate?: string,
			receiptTime?: string
		) => Promise<BoletoEntry>;
		getFn: (id: number) => Promise<BoletoEntry>;
	} = $props();

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------

	let items = $state<BoletoEntry[]>([]);
	let months = $state<string[]>([]);
	let loading = $state(true);
	let filterMonth = $state('');

	// Upload sheet
	let uploadOpen = $state(false);
	let uploadFile = $state<File | null>(null);
	let uploadPreviewing = $state(false);
	let uploadPreview = $state<BoletoPreview | null>(null);
	let uploadFiscalMes = $state('');
	let uploadReceipt = $state<File | null>(null);
	let uploadReceiptPreviewing = $state(false);
	let uploadReceiptPreview = $state<ReceiptPreview | null>(null);
	let uploadReceiptDate = $state('');
	let uploadReceiptTime = $state('');
	let uploadSaving = $state(false);

	// Detail sheet
	let detailOpen = $state(false);
	let detailItem = $state<BoletoEntry | null>(null);
	let barcodeDiff = $state<string | null>(null);
	let barcodeDiffLoading = $state(false);
	let detailEditing = $state(false);
	let detailSaving = $state(false);
	let detailValue = $state('');
	let detailEmissionDate = $state('');
	let detailDeadlineDate = $state('');
	let detailCodigoBarras = $state('');
	let detailCodigoBarrasDigits = $state('');
	let detailReceiptDate = $state('');
	let detailReceiptValue = $state('');
	let detailReceiptCodigoBarras = $state('');
	let detailReceiptCodigoBarrasDigits = $state('');
	let detailFiscalMes = $state('');

	// Detail replacement state
	let replacingPdf = $state(false);
	let replacingReceipt = $state(false);
	let replaceReceiptDate = $state('');
	let replaceReceiptTime = $state('');
	let replaceReceiptFile = $state<File | null>(null);
	let replaceReceiptPreview = $state<ReceiptPreview | null>(null);
	let replaceReceiptPreviewing = $state(false);
	let showReplaceReceiptForm = $state(false);

	let replacePdfInputEl: HTMLInputElement | undefined = $state();
	let replaceReceiptInputEl: HTMLInputElement | undefined = $state();

	// Delete dialog
	let deleteDialogOpen = $state(false);
	let deleteTarget = $state<BoletoEntry | null>(null);

	// Inline fiscal month edit
	let editingFmId = $state<number | null>(null);
	let editingFmValue = $state('');

	// Sorting
	let sortField = $state<string>('emission_date');
	let sortAsc = $state(false);

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
		await loadItems();
	});

	async function loadItems() {
		loading = true;
		try {
			items = await listFn(filterMonth || undefined);
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : `Failed to load ${domainLabel}`
			);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void filterMonth;
		loadItems();
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

	const sortedItems = $derived(() => {
		const arr = [...items];
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
		uploadFile = null;
		uploadPreviewing = false;
		uploadPreview = null;
		uploadFiscalMes = '';
		uploadReceipt = null;
		uploadReceiptPreviewing = false;
		uploadReceiptPreview = null;
		uploadReceiptDate = '';
		uploadReceiptTime = '';
		uploadSaving = false;
	}

	async function handleDocFileSelected(files: File[]) {
		if (files.length === 0) return;
		uploadFile = files[0];
		uploadPreview = null;
		uploadPreviewing = true;
		try {
			uploadPreview = await parsePreviewFn(files[0]);
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Preview failed'
			);
		} finally {
			uploadPreviewing = false;
		}
	}

	async function handleReceiptSelected(files: File[]) {
		if (files.length === 0) return;
		uploadReceipt = files[0];
		uploadReceiptPreview = null;
		uploadReceiptPreviewing = true;
		try {
			uploadReceiptPreview = await receiptParsePreview(files[0]);
			if (uploadReceiptPreview.payment_datetime) {
				const parts = uploadReceiptPreview.payment_datetime.split(' ');
				if (parts[0]) {
					const [dd, mm, yyyy] = parts[0].split('/');
					if (yyyy && mm && dd) uploadReceiptDate = `${yyyy}-${mm}-${dd}`;
				}
				if (parts[1]) uploadReceiptTime = parts[1];
			}
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Receipt preview failed'
			);
		} finally {
			uploadReceiptPreviewing = false;
		}
	}

	async function handleSave() {
		if (!uploadFile || !uploadFiscalMes) {
			toast.error('PDF and fiscal month are required');
			return;
		}
		uploadSaving = true;
		try {
			await createFn(
				uploadFile,
				uploadFiscalMes,
				uploadReceipt ?? undefined,
				uploadReceiptDate || undefined,
				uploadReceiptTime || undefined
			);
			toast.success(`${domainLabel} saved successfully`);
			uploadOpen = false;
			resetUpload();
			await loadItems();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Save failed');
		} finally {
			uploadSaving = false;
		}
	}

	// ---------------------------------------------------------------------------
	// Detail
	// ---------------------------------------------------------------------------

	async function openDetail(item: BoletoEntry) {
		detailItem = item;
		resetDetailEdit(item);
		barcodeDiff = null;
		barcodeDiffLoading = false;
		detailEditing = false;
		detailSaving = false;
		replacingPdf = false;
		replacingReceipt = false;
		replaceReceiptFile = null;
		replaceReceiptPreview = null;
		replaceReceiptPreviewing = false;
		replaceReceiptDate = '';
		replaceReceiptTime = '';
		showReplaceReceiptForm = false;
		detailOpen = true;
	}

	async function refreshDetail() {
		if (!detailItem) return;
		try {
			detailItem = await getFn(detailItem.id);
			if (detailItem && !detailEditing) {
				resetDetailEdit(detailItem);
			}
		} catch {
			// silently fail
		}
	}

	function nullableString(value: string): string | null {
		const v = value.trim();
		return v.length > 0 ? v : null;
	}

	function nullableNumber(value: string): number | null {
		const v = value.trim();
		if (!v) return null;
		const n = Number(v.replace(',', '.'));
		return Number.isFinite(n) ? n : null;
	}

	function resetDetailEdit(item: BoletoEntry) {
		detailValue = item.value == null ? '' : String(item.value);
		detailEmissionDate = item.emission_date ?? '';
		detailDeadlineDate = item.deadline_date ?? '';
		detailCodigoBarras = item.codigo_barras ?? '';
		detailCodigoBarrasDigits = item.codigo_barras_digits ?? '';
		detailReceiptDate = item.receipt_date ?? '';
		detailReceiptValue = item.receipt_value == null ? '' : String(item.receipt_value);
		detailReceiptCodigoBarras = item.receipt_codigo_barras ?? '';
		detailReceiptCodigoBarrasDigits = item.receipt_codigo_barras_digits ?? '';
		detailFiscalMes = item.fiscal_mes ?? '';
	}

	function startDetailEdit() {
		if (!detailItem) return;
		resetDetailEdit(detailItem);
		detailEditing = true;
	}

	function cancelDetailEdit() {
		if (detailItem) resetDetailEdit(detailItem);
		detailEditing = false;
	}

	async function saveDetailEdit() {
		if (!detailItem) return;
		const payload: BoletoLikeFieldsPatch = {
			value: nullableNumber(detailValue),
			emission_date: nullableString(detailEmissionDate),
			deadline_date: nullableString(detailDeadlineDate),
			codigo_barras: nullableString(detailCodigoBarras),
			codigo_barras_digits: nullableString(detailCodigoBarrasDigits),
			receipt_date: nullableString(detailReceiptDate),
			receipt_value: nullableNumber(detailReceiptValue),
			receipt_codigo_barras: nullableString(detailReceiptCodigoBarras),
			receipt_codigo_barras_digits: nullableString(detailReceiptCodigoBarrasDigits),
			fiscal_mes: nullableString(detailFiscalMes)
		};
		detailSaving = true;
		try {
			detailItem = await patchFieldsFn(detailItem.id, payload);
			detailEditing = false;
			barcodeDiff = null;
			toast.success('Fields updated');
			await loadItems();
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Save changes failed'
			);
		} finally {
			detailSaving = false;
		}
	}

	async function loadBarcodeDiff(id: number) {
		barcodeDiffLoading = true;
		try {
			barcodeDiff = await getBarcodeDiffFn(id);
		} catch {
			barcodeDiff = 'Could not load barcode diff.';
		} finally {
			barcodeDiffLoading = false;
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

	// ---------------------------------------------------------------------------
	// Detail: Replace PDF
	// ---------------------------------------------------------------------------

	async function handleReplacePdf(files: File[]) {
		if (!detailItem || files.length === 0) return;
		replacingPdf = true;
		try {
			detailItem = await replacePdfFn(detailItem.id, files[0]);
			toast.success(`${domainLabel} PDF replaced`);
			barcodeDiff = null;
			await loadItems();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Replace failed');
		} finally {
			replacingPdf = false;
		}
	}

	// ---------------------------------------------------------------------------
	// Detail: Replace/Add Receipt
	// ---------------------------------------------------------------------------

	async function handleDetailReceiptSelected(files: File[]) {
		if (files.length === 0) return;
		showReplaceReceiptForm = true;
		replaceReceiptFile = files[0];
		replaceReceiptPreview = null;
		replaceReceiptPreviewing = true;
		try {
			replaceReceiptPreview = await receiptParsePreview(files[0]);
			if (replaceReceiptPreview.payment_datetime) {
				const parts = replaceReceiptPreview.payment_datetime.split(' ');
				if (parts[0]) {
					const [dd, mm, yyyy] = parts[0].split('/');
					if (yyyy && mm && dd) replaceReceiptDate = `${yyyy}-${mm}-${dd}`;
				}
				if (parts[1]) replaceReceiptTime = parts[1];
			}
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Receipt preview failed'
			);
		} finally {
			replaceReceiptPreviewing = false;
		}
	}

	async function handleSaveReceipt() {
		if (!detailItem || !replaceReceiptFile) return;
		replacingReceipt = true;
		try {
			detailItem = await replaceReceiptFn(
				detailItem.id,
				replaceReceiptFile,
				replaceReceiptDate || undefined,
				replaceReceiptTime || undefined
			);
			toast.success('Receipt updated');
			replaceReceiptFile = null;
			replaceReceiptPreview = null;
			replaceReceiptDate = '';
			replaceReceiptTime = '';
			showReplaceReceiptForm = false;
			barcodeDiff = null;
			await loadItems();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Receipt update failed');
		} finally {
			replacingReceipt = false;
		}
	}

	function openReplacePdfPicker() {
		replacePdfInputEl?.click();
	}

	function openReplaceReceiptPicker() {
		showReplaceReceiptForm = true;
		replaceReceiptInputEl?.click();
	}

	function cancelReplaceReceipt() {
		showReplaceReceiptForm = false;
		replaceReceiptFile = null;
		replaceReceiptPreview = null;
		replaceReceiptPreviewing = false;
		replaceReceiptDate = '';
		replaceReceiptTime = '';
	}

	function handleReplacePdfInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		void handleReplacePdf(Array.from(target.files ?? []));
		target.value = '';
	}

	function handleReplaceReceiptInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		void handleDetailReceiptSelected(Array.from(target.files ?? []));
		target.value = '';
	}

	// ---------------------------------------------------------------------------
	// Inline fiscal month edit
	// ---------------------------------------------------------------------------

	function startEditFm(item: BoletoEntry) {
		editingFmId = item.id;
		editingFmValue = item.fiscal_mes ?? '';
	}

	async function saveFm(id: number) {
		try {
			await patchFiscalMesFn(id, editingFmValue || null);
			toast.success('Fiscal month updated');
			editingFmId = null;
			await loadItems();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Update failed');
		}
	}

	// ---------------------------------------------------------------------------
	// Delete
	// ---------------------------------------------------------------------------

	function confirmDelete(item: BoletoEntry) {
		deleteTarget = item;
		deleteDialogOpen = true;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		try {
			await deleteFn(deleteTarget.id);
			toast.success(`${domainLabel} deleted`);
			deleteTarget = null;
			await loadItems();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Delete failed');
		}
	}

	function receiptStatusDisplay(
		receiptPath: string | null,
		matchStatus: string | null
	): { status: 'success' | 'warning' | 'error' | 'neutral'; label: string } {
		if (!receiptPath) return { status: 'neutral', label: 'No receipt' };
		if (matchStatus === 'match') return { status: 'success', label: 'Match' };
		if (matchStatus === 'mismatch') return { status: 'error', label: 'Mismatch' };
		return { status: 'warning', label: 'Unverified' };
	}
</script>

<div class="space-y-6">
	<PageHeader title={domainLabel} description={`Manage ${domainLabel.toLowerCase()} and receipts`}>
		{#snippet actions()}
			<Button onclick={() => { resetUpload(); uploadOpen = true; }}>
				<Plus class="h-4 w-4" />
				Upload {domainLabel}
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
	{:else if items.length === 0}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<p class="text-muted-foreground">No {domainLabel.toLowerCase()} found.</p>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="rounded-lg border">
			<Table.Table>
				<Table.TableHeader>
					<Table.TableRow>
						{#each [
							{ key: 'value', label: 'Value' },
							{ key: 'emission_date', label: 'Emission' },
							{ key: 'deadline_date', label: 'Deadline' },
							{ key: 'receipt_match_status', label: 'Receipt' },
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
					{#each sortedItems() as item (item.id)}
						{@const ms = receiptStatusDisplay(item.receipt_path, item.receipt_match_status)}
						<Table.TableRow>
							<Table.TableCell class="tabular-nums">{formatBrl(item.value)}</Table.TableCell>
							<Table.TableCell class="tabular-nums">{formatDateBr(item.emission_date)}</Table.TableCell>
							<Table.TableCell class="tabular-nums">{formatDateBr(item.deadline_date)}</Table.TableCell>
							<Table.TableCell>
								<StatusBadge status={ms.status} label={ms.label} />
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
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => downloadFile(`/${routePrefix}/${item.id}/pdf`, `${routePrefix}_${item.id}.pdf`)} title="Download PDF">
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
			<Sheet.SheetTitle>Upload {domainLabel}</Sheet.SheetTitle>
			<Sheet.SheetDescription>Upload a PDF and optional receipt.</Sheet.SheetDescription>
		</Sheet.SheetHeader>
		<div class="flex-1 overflow-y-auto px-6 py-4 space-y-6">
			<!-- Document PDF -->
			<div class="space-y-2">
				<span class="text-sm font-medium">{domainLabel} PDF</span>
				<FileDropZone
					accept=".pdf,application/pdf"
					loading={uploadPreviewing}
					bind:file={uploadFile}
					onchange={handleDocFileSelected}
					label={`Drop ${domainLabel} PDF here`}
				/>
			</div>

			{#if uploadPreview}
				<Card.Root>
					<Card.Header class="pb-3">
						<Card.Title class="text-sm">Extracted Data</Card.Title>
					</Card.Header>
					<Card.Content>
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Value</dt>
							<dd class="tabular-nums">{formatBrl(uploadPreview.value)}</dd>
							<dt class="text-muted-foreground">Emission</dt>
							<dd>{formatDateBr(uploadPreview.emission_date)}</dd>
							<dt class="text-muted-foreground">Deadline</dt>
							<dd>{formatDateBr(uploadPreview.deadline_date)}</dd>
							<dt class="text-muted-foreground">Barcode</dt>
							<dd class="font-mono text-xs truncate">{uploadPreview.codigo_barras_digits ?? '\u2014'}</dd>
						</dl>
					</Card.Content>
				</Card.Root>

				<!-- Receipt (optional) -->
				<div class="space-y-2">
					<span class="text-sm font-medium">Receipt Image (optional)</span>
					<FileDropZone
						accept="image/*"
						loading={uploadReceiptPreviewing}
						bind:file={uploadReceipt}
						onchange={handleReceiptSelected}
						label="Drop receipt image here"
					/>
				</div>

				{#if uploadReceiptPreview}
					<Card.Root>
						<Card.Header class="pb-3">
							<Card.Title class="text-sm">Receipt Data</Card.Title>
						</Card.Header>
						<Card.Content>
							<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
								<dt class="text-muted-foreground">Value</dt>
								<dd class="tabular-nums">{formatBrl(uploadReceiptPreview.value)}</dd>
								<dt class="text-muted-foreground">Date/Time</dt>
								<dd>{uploadReceiptPreview.payment_datetime ?? '\u2014'}</dd>
								<dt class="text-muted-foreground">Barcode</dt>
								<dd class="font-mono text-xs truncate">{uploadReceiptPreview.codigo_barras_digits ?? '\u2014'}</dd>
							</dl>
						</Card.Content>
					</Card.Root>
				{/if}

				{#if uploadReceipt}
					<div class="grid grid-cols-2 gap-3">
						<div class="space-y-1">
							<span class="text-xs font-medium text-muted-foreground">Receipt Date</span>
							<Input type="date" bind:value={uploadReceiptDate} />
						</div>
						<div class="space-y-1">
							<span class="text-xs font-medium text-muted-foreground">Receipt Time</span>
							<Input type="time" step="1" bind:value={uploadReceiptTime} />
						</div>
					</div>
				{/if}

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
						Save {domainLabel}
					{/if}
				</Button>
			</Sheet.SheetFooter>
		{/if}
	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- Detail Sheet -->
<Sheet.Sheet bind:open={detailOpen}>
	<Sheet.SheetContent side="right" class="sm:max-w-2xl">
		<Sheet.SheetHeader class="gap-2 pt-5 pr-14 pb-1">
			<div class="flex items-start justify-between gap-3">
				<div class="space-y-1">
					<Sheet.SheetTitle>{domainLabel} Details</Sheet.SheetTitle>
					{#if detailItem}
						<Sheet.SheetDescription>ID: {detailItem.id} &middot; {formatFiscalMes(detailItem.fiscal_mes)}</Sheet.SheetDescription>
					{/if}
				</div>
				{#if detailItem}
					<div class="flex items-center gap-2 shrink-0">
						{#if detailEditing}
							<Button variant="outline" size="sm" onclick={cancelDetailEdit} disabled={detailSaving}>
								Cancel
							</Button>
							<Button size="sm" onclick={saveDetailEdit} disabled={detailSaving}>
								{#if detailSaving}
									<Loader2 class="h-4 w-4 animate-spin" />
									Saving...
								{:else}
									Save changes
								{/if}
							</Button>
						{:else}
							<Button variant="outline" size="sm" onclick={startDetailEdit}>
								<Pencil class="h-4 w-4" />
								Edit fields
							</Button>
						{/if}
					</div>
				{/if}
			</div>
		</Sheet.SheetHeader>
		{#if detailItem}
			<div class="flex-1 overflow-y-auto px-6 py-2 space-y-5">
				<!-- Document Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<FileText class="h-4 w-4 text-muted-foreground" />
								<Card.Title class="text-sm">{domainLabel} Document</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title={`Replace ${domainLabel} PDF`}
									onclick={openReplacePdfPicker}
									disabled={replacingPdf}
								>
									{#if replacingPdf}
										<Loader2 class="h-3.5 w-3.5 animate-spin" />
									{:else}
										<Pencil class="h-3.5 w-3.5" />
									{/if}
								</Button>
							</div>
							<Button
								variant="outline"
								size="sm"
								class="h-7 text-xs"
								onclick={() => downloadFile(`/${routePrefix}/${detailItem!.id}/pdf`, `${routePrefix}_${detailItem!.id}.pdf`)}
							>
								<Download class="h-3.5 w-3.5" />
								PDF
							</Button>
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Value</dt>
							<dd class="tabular-nums font-medium">
								{#if detailEditing}
									<Input type="number" step="0.01" bind:value={detailValue} class="h-8 text-xs" />
								{:else}
									{formatBrl(detailItem.value)}
								{/if}
							</dd>
							<dt class="text-muted-foreground">Emission</dt>
							<dd class="tabular-nums">
								{#if detailEditing}
									<Input type="text" bind:value={detailEmissionDate} placeholder="DD/MM/YYYY" class="h-8 text-xs" />
								{:else}
									{formatDateBr(detailItem.emission_date)}
								{/if}
							</dd>
							<dt class="text-muted-foreground">Deadline</dt>
							<dd class="tabular-nums">
								{#if detailEditing}
									<Input type="text" bind:value={detailDeadlineDate} placeholder="DD/MM/YYYY" class="h-8 text-xs" />
								{:else}
									{formatDateBr(detailItem.deadline_date)}
								{/if}
							</dd>
							<dt class="text-muted-foreground">Barcode</dt>
							<dd class="font-mono text-xs break-all">
								{#if detailEditing}
									<Input type="text" bind:value={detailCodigoBarrasDigits} class="h-8 text-xs font-mono" />
								{:else}
									{detailItem.codigo_barras_digits ?? '\u2014'}
								{/if}
							</dd>
							<dt class="text-muted-foreground">Barcode (Raw)</dt>
							<dd class="font-mono text-xs break-all">
								{#if detailEditing}
									<Input type="text" bind:value={detailCodigoBarras} class="h-8 text-xs font-mono" />
								{:else}
									{detailItem.codigo_barras ?? '\u2014'}
								{/if}
							</dd>
							<dt class="text-muted-foreground">Fiscal Month</dt>
							<dd>
								{#if detailEditing}
									<FiscalMonthPicker bind:value={detailFiscalMes} {months} />
								{:else}
									{formatFiscalMes(detailItem.fiscal_mes)}
								{/if}
							</dd>
							<dt class="text-muted-foreground">Created</dt>
							<dd class="text-xs">{detailItem.created_at ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Updated</dt>
							<dd class="text-xs">{detailItem.updated_at ?? '\u2014'}</dd>
						</dl>
					</Card.Content>
					<input
						bind:this={replacePdfInputEl}
						type="file"
						accept=".pdf,application/pdf"
						class="sr-only"
						onchange={handleReplacePdfInputChange}
					/>
				</Card.Root>

				<!-- Receipt Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<Receipt class="h-4 w-4 text-muted-foreground" />
								<Card.Title class="text-sm">Receipt</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title={detailItem.receipt_path ? 'Replace receipt image' : 'Add receipt image'}
									onclick={openReplaceReceiptPicker}
									disabled={replacingReceipt || replaceReceiptPreviewing}
								>
									{#if replacingReceipt || replaceReceiptPreviewing}
										<Loader2 class="h-3.5 w-3.5 animate-spin" />
									{:else}
										<Pencil class="h-3.5 w-3.5" />
									{/if}
								</Button>
							</div>
							{#if detailItem.receipt_path}
								{@const ms = receiptStatusDisplay(detailItem.receipt_path, detailItem.receipt_match_status)}
								<div class="flex items-center gap-2">
									<StatusBadge status={ms.status} label={ms.label} />
									<Button
										variant="outline"
										size="sm"
										class="h-7 text-xs"
										onclick={() => downloadFile(`/${routePrefix}/${detailItem!.id}/receipt`, `receipt_${detailItem!.id}`)}
									>
										<Download class="h-3.5 w-3.5" />
										Image
									</Button>
								</div>
							{/if}
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						{#if detailItem.receipt_path}
							<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
								<dt class="text-muted-foreground">Value</dt>
								<dd class="tabular-nums">
									{#if detailEditing}
										<Input type="number" step="0.01" bind:value={detailReceiptValue} class="h-8 text-xs" />
									{:else}
										{formatBrl(detailItem.receipt_value)}
									{/if}
								</dd>
								<dt class="text-muted-foreground">Date</dt>
								<dd>
									{#if detailEditing}
										<Input type="text" bind:value={detailReceiptDate} placeholder="DD/MM/YYYY HH:MM:SS" class="h-8 text-xs" />
									{:else}
										{formatDateBr(detailItem.receipt_date)}
									{/if}
								</dd>
								<dt class="text-muted-foreground">Barcode</dt>
								<dd class="font-mono text-xs break-all">
									{#if detailEditing}
										<Input type="text" bind:value={detailReceiptCodigoBarrasDigits} class="h-8 text-xs font-mono" />
									{:else}
										{detailItem.receipt_codigo_barras_digits ?? '\u2014'}
									{/if}
								</dd>
								<dt class="text-muted-foreground">Barcode (Raw)</dt>
								<dd class="font-mono text-xs break-all">
									{#if detailEditing}
										<Input type="text" bind:value={detailReceiptCodigoBarras} class="h-8 text-xs font-mono" />
									{:else}
										{detailItem.receipt_codigo_barras ?? '\u2014'}
									{/if}
								</dd>
							</dl>

							{#if detailItem.receipt_match_status === 'mismatch'}
								<div>
									{#if barcodeDiff === null && !barcodeDiffLoading}
										<Button
											variant="outline"
											size="sm"
											onclick={() => loadBarcodeDiff(detailItem!.id)}
										>
											<FileWarning class="h-4 w-4" />
											View Barcode Diff
										</Button>
									{:else if barcodeDiffLoading}
										<Loader2 class="h-4 w-4 animate-spin text-muted-foreground" />
									{:else}
										<pre class="rounded-md bg-muted p-3 text-xs font-mono whitespace-pre-wrap overflow-x-auto">{barcodeDiff}</pre>
									{/if}
								</div>
							{/if}
						{:else}
							<p class="text-sm text-muted-foreground">No receipt attached.</p>
						{/if}

						{#if showReplaceReceiptForm}
							<div class="space-y-3 rounded-md border p-3">
								<div class="flex items-center justify-between">
									<span class="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
										<RefreshCw class="h-3 w-3" />
										{detailItem.receipt_path ? 'Replace Receipt' : 'Add Receipt'}
									</span>
									<Button variant="outline" size="sm" class="h-7 text-xs" onclick={openReplaceReceiptPicker}>
										Choose Image
									</Button>
								</div>

								{#if replaceReceiptPreview}
									<div class="rounded-md border p-3 space-y-2">
										<dl class="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
											<dt class="text-muted-foreground">Value</dt>
											<dd class="tabular-nums">{formatBrl(replaceReceiptPreview.value)}</dd>
											<dt class="text-muted-foreground">Date/Time</dt>
											<dd>{replaceReceiptPreview.payment_datetime ?? '\u2014'}</dd>
											<dt class="text-muted-foreground">Barcode</dt>
											<dd class="font-mono break-all">{replaceReceiptPreview.codigo_barras_digits ?? '\u2014'}</dd>
										</dl>
									</div>
								{/if}

								{#if replaceReceiptFile}
									<div class="grid grid-cols-2 gap-3">
										<div class="space-y-1">
											<span class="text-xs font-medium text-muted-foreground">Receipt Date</span>
											<Input type="date" bind:value={replaceReceiptDate} class="h-8 text-xs" />
										</div>
										<div class="space-y-1">
											<span class="text-xs font-medium text-muted-foreground">Receipt Time</span>
											<Input type="time" step="1" bind:value={replaceReceiptTime} class="h-8 text-xs" />
										</div>
									</div>
									<div class="flex items-center gap-2">
										<Button
											onclick={handleSaveReceipt}
											disabled={replacingReceipt}
											size="sm"
											class="flex-1"
										>
											{#if replacingReceipt}
												<Loader2 class="h-4 w-4 animate-spin" />
												Saving...
											{:else}
												Save Receipt
											{/if}
										</Button>
										<Button
											variant="ghost"
											size="sm"
											class="h-8"
											onclick={cancelReplaceReceipt}
											disabled={replacingReceipt}
										>
											Cancel
										</Button>
									</div>
								{/if}
							</div>
						{/if}
						<input
							bind:this={replaceReceiptInputEl}
							type="file"
							accept="image/*"
							class="sr-only"
							onchange={handleReplaceReceiptInputChange}
						/>
					</Card.Content>
				</Card.Root>
			</div>
		{/if}
	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- Delete confirmation -->
<ConfirmDialog
	bind:open={deleteDialogOpen}
	title={`Delete ${domainLabel}`}
	description={`This will permanently remove the ${domainLabel.toLowerCase()}, its PDF, and receipt.`}
	onconfirm={handleDelete}
/>
