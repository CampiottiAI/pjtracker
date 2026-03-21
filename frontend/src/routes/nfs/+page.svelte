<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		formatApiErrorMessage,
		listNfs,
		listFiscalMonths,
		deleteNf,
		patchNfFiscalMes,
		nfParsePreview,
		createNf,
		getNfImages,
		downloadBlob,
		triggerDownload
	} from '$lib/api/client.js';
	import type { NfEntry, NfPreview, NfImage } from '$lib/api/types.js';
	import { cn } from '$lib/utils.js';
	import {
		formatFiscalMes,
		formatUsd,
		formatBrl,
		formatNumber,
		formatPercent,
		formatDateBr
	} from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import FiscalMonthPicker from '$lib/components/FiscalMonthPicker.svelte';
	import FileDropZone from '$lib/components/FileDropZone.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import {
		Plus,
		Download,
		Trash2,
		Eye,
		Image as ImageIcon,
		Loader2,
		ArrowUpDown
	} from 'lucide-svelte';

	// ---------------------------------------------------------------------------
	// State
	// ---------------------------------------------------------------------------

	let nfs = $state<NfEntry[]>([]);
	let months = $state<string[]>([]);
	let loading = $state(true);
	let filterMonth = $state('');
	let filterDateFrom = $state('');
	let filterDateTo = $state('');

	// Upload sheet
	let uploadOpen = $state(false);
	let uploadFile = $state<File | null>(null);
	let uploadImages = $state<File[]>([]);
	let uploadPreviewing = $state(false);
	let uploadPreview = $state<NfPreview | null>(null);
	let uploadFiscalMes = $state('');
	let uploadSaving = $state(false);

	// Detail sheet
	let detailOpen = $state(false);
	let detailNf = $state<NfEntry | null>(null);
	let detailImages = $state<NfImage[]>([]);

	// Delete dialog
	let deleteDialogOpen = $state(false);
	let deleteTarget = $state<NfEntry | null>(null);

	// Inline fiscal month edit
	let editingFmId = $state<number | null>(null);
	let editingFmValue = $state('');

	// Sorting
	let sortField = $state<string>('nf_date');
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
		await loadNfs();
	});

	async function loadNfs() {
		loading = true;
		try {
			const params: Record<string, string> = {};
			if (filterMonth) params.fiscal_mes = filterMonth;
			else {
				if (filterDateFrom) params.date_from = filterDateFrom;
				if (filterDateTo) params.date_to = filterDateTo;
			}
			nfs = await listNfs(params);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load NFs');
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		// Re-fetch when filters change (dependencies tracked automatically)
		void filterMonth;
		void filterDateFrom;
		void filterDateTo;
		loadNfs();
	});

	// ---------------------------------------------------------------------------
	// Sorting
	// ---------------------------------------------------------------------------

	function toggleSort(field: string) {
		if (sortField === field) {
			sortAsc = !sortAsc;
		} else {
			sortField = field;
			sortAsc = true;
		}
	}

	const sortedNfs = $derived(() => {
		const arr = [...nfs];
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
	// Upload flow
	// ---------------------------------------------------------------------------

	function resetUpload() {
		uploadFile = null;
		uploadImages = [];
		uploadPreviewing = false;
		uploadPreview = null;
		uploadFiscalMes = '';
		uploadSaving = false;
	}

	async function handleFileSelected(files: File[]) {
		if (files.length === 0) return;
		uploadFile = files[0];
		uploadPreview = null;
		uploadPreviewing = true;
		try {
			uploadPreview = await nfParsePreview(files[0]);
			if (uploadPreview.brl == null) {
				toast.warning('Could not extract USD/rate from this PDF');
			}
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Preview failed'
			);
			uploadPreview = null;
		} finally {
			uploadPreviewing = false;
		}
	}

	async function handleSave() {
		if (!uploadFile || !uploadFiscalMes) {
			toast.error('PDF and fiscal month are required');
			return;
		}
		uploadSaving = true;
		try {
			await createNf(uploadFile, uploadFiscalMes, uploadImages.length > 0 ? uploadImages : undefined);
			toast.success('NF saved successfully');
			uploadOpen = false;
			resetUpload();
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Save failed');
		} finally {
			uploadSaving = false;
		}
	}

	// ---------------------------------------------------------------------------
	// Detail
	// ---------------------------------------------------------------------------

	async function openDetail(nf: NfEntry) {
		detailNf = nf;
		detailImages = [];
		detailOpen = true;
		try {
			detailImages = await getNfImages(nf.id);
		} catch {
			// images may be empty
		}
	}

	async function downloadPdf(nfId: number) {
		try {
			const { blob, filename } = await downloadBlob(`/nfs/${nfId}/pdf`);
			triggerDownload(blob, filename ?? `nf_${nfId}.pdf`);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Download failed');
		}
	}

	async function downloadImage(nfId: number, imageId: number) {
		try {
			const { blob, filename } = await downloadBlob(`/nfs/${nfId}/images/${imageId}`);
			triggerDownload(blob, filename ?? `nf_${nfId}_img_${imageId}`);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Download failed');
		}
	}

	// ---------------------------------------------------------------------------
	// Inline fiscal month edit
	// ---------------------------------------------------------------------------

	function startEditFm(nf: NfEntry) {
		editingFmId = nf.id;
		editingFmValue = nf.fiscal_mes ?? '';
	}

	async function saveFm(nfId: number) {
		try {
			await patchNfFiscalMes(nfId, editingFmValue || null);
			toast.success('Fiscal month updated');
			editingFmId = null;
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Update failed');
		}
	}

	// ---------------------------------------------------------------------------
	// Delete
	// ---------------------------------------------------------------------------

	function confirmDelete(nf: NfEntry) {
		deleteTarget = nf;
		deleteDialogOpen = true;
	}

	async function handleDelete() {
		if (!deleteTarget) return;
		try {
			await deleteNf(deleteTarget.id);
			toast.success('NF deleted');
			deleteTarget = null;
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Delete failed');
		}
	}
</script>

<div class="space-y-6">
	<PageHeader title="Notas Fiscais" description="Manage NF-e documents">
		{#snippet actions()}
			<Button onclick={() => { resetUpload(); uploadOpen = true; }}>
				<Plus class="h-4 w-4" />
				Upload NF
			</Button>
		{/snippet}
	</PageHeader>

	<!-- Filters -->
	<div class="flex flex-wrap items-end gap-3">
		<div class="space-y-1">
			<span class="text-xs font-medium text-muted-foreground">Fiscal Month</span>
			<FiscalMonthPicker bind:value={filterMonth} {months} />
		</div>
		{#if !filterMonth}
			<div class="space-y-1">
				<label for="nf-date-from" class="text-xs font-medium text-muted-foreground">From</label>
				<Input id="nf-date-from" type="date" bind:value={filterDateFrom} class="w-40" />
			</div>
			<div class="space-y-1">
				<label for="nf-date-to" class="text-xs font-medium text-muted-foreground">To</label>
				<Input id="nf-date-to" type="date" bind:value={filterDateTo} class="w-40" />
			</div>
		{/if}
	</div>

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
		</div>
	{:else if nfs.length === 0}
		<Card.Root>
			<Card.Content class="py-12 text-center">
				<p class="text-muted-foreground">No notas fiscais found.</p>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="rounded-lg border">
			<Table.Table>
				<Table.TableHeader>
					<Table.TableRow>
						{#each [
							{ key: 'nf_date', label: 'Date' },
							{ key: 'company', label: 'Company' },
							{ key: 'usd', label: 'USD' },
							{ key: 'rate', label: 'Rate' },
							{ key: 'spread', label: 'Spread' },
							{ key: 'brl_with_spread', label: 'BRL' },
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
					{#each sortedNfs() as nf (nf.id)}
						<Table.TableRow>
							<Table.TableCell class="tabular-nums">{formatDateBr(nf.nf_date)}</Table.TableCell>
							<Table.TableCell>{nf.company ?? '\u2014'}</Table.TableCell>
							<Table.TableCell class="tabular-nums">{formatUsd(nf.usd)}</Table.TableCell>
							<Table.TableCell class="tabular-nums">{formatNumber(nf.rate, 4)}</Table.TableCell>
							<Table.TableCell class="tabular-nums">{formatPercent(nf.spread)}</Table.TableCell>
							<Table.TableCell class="tabular-nums font-medium">{formatBrl(nf.brl_with_spread)}</Table.TableCell>
							<Table.TableCell>
								{#if editingFmId === nf.id}
									<div class="flex items-center gap-1">
										<Input
											type="text"
											bind:value={editingFmValue}
											placeholder="YYYY-MM"
											class="h-7 w-24 text-xs"
											onkeydown={(e: KeyboardEvent) => {
												if (e.key === 'Enter') saveFm(nf.id);
												if (e.key === 'Escape') editingFmId = null;
											}}
										/>
										<Button variant="ghost" size="sm" class="h-7 px-2 text-xs" onclick={() => saveFm(nf.id)}>
											OK
										</Button>
									</div>
								{:else}
									<button
										class="text-sm hover:underline"
										onclick={() => startEditFm(nf)}
										title="Click to edit fiscal month"
									>
										{formatFiscalMes(nf.fiscal_mes)}
									</button>
								{/if}
							</Table.TableCell>
							<Table.TableCell>
								<div class="flex items-center gap-1">
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => openDetail(nf)} title="View details">
										<Eye class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => downloadPdf(nf.id)} title="Download PDF">
										<Download class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7 text-destructive-foreground" onclick={() => confirmDelete(nf)} title="Delete">
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
			<Sheet.SheetTitle>Upload Nota Fiscal</Sheet.SheetTitle>
			<Sheet.SheetDescription>Upload a NF PDF to extract data and save.</Sheet.SheetDescription>
		</Sheet.SheetHeader>
		<div class="flex-1 overflow-y-auto px-6 py-4 space-y-6">
			<!-- PDF drop zone -->
			<div class="space-y-2">
				<span class="text-sm font-medium">NF PDF</span>
				<FileDropZone
					accept=".pdf,application/pdf"
					loading={uploadPreviewing}
					bind:file={uploadFile}
					onchange={handleFileSelected}
					label="Drop NF PDF here"
				/>
			</div>

			<!-- Preview card -->
			{#if uploadPreview}
				<Card.Root>
					<Card.Header class="pb-3">
						<Card.Title class="text-sm">Extracted Data</Card.Title>
					</Card.Header>
					<Card.Content>
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Company</dt>
							<dd>{uploadPreview.company ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">USD</dt>
							<dd class="tabular-nums">{formatUsd(uploadPreview.usd)}</dd>
							<dt class="text-muted-foreground">Rate</dt>
							<dd class="tabular-nums">{formatNumber(uploadPreview.rate, 4)}</dd>
							<dt class="text-muted-foreground">Spread</dt>
							<dd class="tabular-nums">
								{formatPercent(uploadPreview.spread)}
								{#if uploadPreview.spread_was_default}
									<Badge variant="outline" class="ml-1 text-[10px] px-1">default</Badge>
								{/if}
							</dd>
							{#if uploadPreview.brl}
								<dt class="text-muted-foreground">BRL (no spread)</dt>
								<dd class="tabular-nums">{formatBrl(uploadPreview.brl.brl_no_spread)}</dd>
								<dt class="text-muted-foreground">BRL (with spread)</dt>
								<dd class="tabular-nums font-medium">{formatBrl(uploadPreview.brl.brl_with_spread)}</dd>
							{/if}
							<dt class="text-muted-foreground">Date</dt>
							<dd>{formatDateBr(uploadPreview.nf_date)}</dd>
							<dt class="text-muted-foreground">Verification Code</dt>
							<dd class="font-mono text-xs">{uploadPreview.verification_code ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Payment Via</dt>
							<dd>{uploadPreview.payment_via ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Source</dt>
							<dd>
								<Badge variant="secondary" class="text-xs">{uploadPreview.source}</Badge>
							</dd>
						</dl>
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Fiscal month picker -->
			{#if uploadPreview}
				<div class="space-y-2">
					<span class="text-sm font-medium">Fiscal Month <span class="text-destructive-foreground">*</span></span>
					<FiscalMonthPicker bind:value={uploadFiscalMes} {months} />
				</div>

				<!-- Image attachments -->
				<div class="space-y-2">
					<span class="text-sm font-medium">Image Attachments (optional)</span>
					<FileDropZone
						accept="image/*"
						multiple={true}
						bind:files={uploadImages}
						label="Drop images here"
					/>
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
						Save NF
					{/if}
				</Button>
			</Sheet.SheetFooter>
		{/if}
	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- Detail Sheet -->
<Sheet.Sheet bind:open={detailOpen}>
	<Sheet.SheetContent side="right">
		<Sheet.SheetHeader>
			<Sheet.SheetTitle>NF Details</Sheet.SheetTitle>
			{#if detailNf}
				<Sheet.SheetDescription>ID: {detailNf.id}</Sheet.SheetDescription>
			{/if}
		</Sheet.SheetHeader>
		{#if detailNf}
			<div class="flex-1 overflow-y-auto px-6 py-4 space-y-6">
				<dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
					<dt class="text-muted-foreground">Company</dt>
					<dd>{detailNf.company ?? '\u2014'}</dd>
					<dt class="text-muted-foreground">USD</dt>
					<dd class="tabular-nums">{formatUsd(detailNf.usd)}</dd>
					<dt class="text-muted-foreground">Rate</dt>
					<dd class="tabular-nums">{formatNumber(detailNf.rate, 4)}</dd>
					<dt class="text-muted-foreground">Spread</dt>
					<dd class="tabular-nums">{formatPercent(detailNf.spread)}</dd>
					<dt class="text-muted-foreground">BRL (no spread)</dt>
					<dd class="tabular-nums">{formatBrl(detailNf.brl_no_spread)}</dd>
					<dt class="text-muted-foreground">BRL (with spread)</dt>
					<dd class="tabular-nums font-medium">{formatBrl(detailNf.brl_with_spread)}</dd>
					<dt class="text-muted-foreground">Date</dt>
					<dd>{formatDateBr(detailNf.nf_date)}</dd>
					<dt class="text-muted-foreground">Verification Code</dt>
					<dd class="font-mono text-xs">{detailNf.verification_code ?? '\u2014'}</dd>
					<dt class="text-muted-foreground">Payment Via</dt>
					<dd>{detailNf.payment_via ?? '\u2014'}</dd>
					<dt class="text-muted-foreground">Fiscal Month</dt>
					<dd>{formatFiscalMes(detailNf.fiscal_mes)}</dd>
					<dt class="text-muted-foreground">Created</dt>
					<dd class="text-xs">{detailNf.created_at}</dd>
				</dl>

				<div class="flex gap-2">
					<Button variant="outline" size="sm" onclick={() => downloadPdf(detailNf!.id)}>
						<Download class="h-4 w-4" />
						Download PDF
					</Button>
				</div>

				{#if detailImages.length > 0}
					<div class="space-y-2">
						<h4 class="text-sm font-medium flex items-center gap-1.5">
							<ImageIcon class="h-4 w-4" />
							Attachments ({detailImages.length})
						</h4>
						<div class="grid grid-cols-2 gap-2">
							{#each detailImages as img}
								<button
									class="rounded-md border border-border p-2 text-xs text-muted-foreground hover:bg-accent transition-colors text-left truncate"
									onclick={() => downloadImage(detailNf!.id, img.id)}
								>
									Image #{img.id}
								</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</Sheet.SheetContent>
</Sheet.Sheet>

<!-- Delete confirmation -->
<ConfirmDialog
	bind:open={deleteDialogOpen}
	title="Delete Nota Fiscal"
	description="This will permanently remove the NF, its PDF, and all attached images."
	onconfirm={handleDelete}
/>
