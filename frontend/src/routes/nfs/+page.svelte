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
		patchNfSpread,
		nfParsePreview,
		createNf,
		getNf,
		getNfImages,
		updateNfPdf,
		addNfImages,
		deleteNfImage,
		downloadBlob,
		triggerDownload
	} from '$lib/api/client.js';
	import type { NfEntry, NfPreview, NfImage } from '$lib/api/types.js';
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
	import UploadActions from '$lib/components/UploadActions.svelte';
	import UploadSteps from '$lib/components/UploadSteps.svelte';
	import UploadFiles from '$lib/components/UploadFiles.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import FilePreviewDialog from '$lib/components/FilePreviewDialog.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import {
		Plus,
		Download,
		Trash2,
		Eye,
		Image as ImageIcon,
		Loader2,
		ArrowUpDown,
		FileText,
		Pencil
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
	let uploadSpread = $state('');
	const uploadSpreadValid = $derived(validSpread(uploadSpread));
	const uploadBrl = $derived(
		uploadPreview?.usd != null && uploadPreview?.rate != null && uploadSpreadValid
			? Math.round(uploadPreview.usd * uploadPreview.rate * (1 - Number(uploadSpread) / 100) * 100) / 100
			: null
	);

	// Detail sheet
	let detailOpen = $state(false);
	let detailNf = $state<NfEntry | null>(null);
	let detailImages = $state<NfImage[]>([]);
	let detailSpread = $state('');
	let savingSpread = $state(false);

	function validSpread(value: string): boolean {
		return String(value).trim() !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 100;
	}

	// File preview
	let previewOpen = $state(false);
	let previewPath = $state<string | null>(null);
	let previewTitle = $state('Visualização');
	let previewFallback = $state('file');

	// Detail replacement state
	let replacingPdf = $state(false);
	let addingImages = $state(false);
	let replacePdfInputEl: HTMLInputElement | undefined = $state();

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
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar notas fiscais');
		} finally {
			loading = false;
		}
	}

	$effect(() => {
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

	let uploadRevision = 0;

	function invalidateUpload() {
		uploadRevision += 1;
		uploadPreview = null;
		uploadSpread = '';
	}

	function resetUpload() {
		invalidateUpload();
		uploadFile = null;
		uploadImages = [];
		uploadPreviewing = false;
		uploadPreview = null;
		uploadFiscalMes = '';
		uploadSpread = '';
		uploadSaving = false;
	}

	function openUpload() {
		resetUpload();
		uploadFiscalMes = filterMonth;
		uploadOpen = true;
	}

	async function handlePreview() {
		if (!uploadFile || uploadPreviewing || uploadSaving) return;
		const revision = uploadRevision;
		uploadPreviewing = true;
		try {
			const preview = await nfParsePreview(uploadFile);
			if (revision !== uploadRevision) return;
			uploadPreview = preview;
			uploadSpread = preview.spread == null ? '' : String(preview.spread);
			if (preview.brl == null) toast.warning('Não foi possível extrair o valor em USD e a cotação deste PDF');
		} catch (e) {
			if (revision === uploadRevision) {
				toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao processar o documento');
			}
		} finally {
			if (revision === uploadRevision) uploadPreviewing = false;
		}
	}

	async function handleSave() {
		if (uploadPreviewing || uploadSaving) return;
		if (!uploadPreview?.brl || !validSpread(uploadSpread)) return;
		if (!uploadFile || !uploadFiscalMes) {
			toast.error('Selecione o PDF e o mês fiscal');
			return;
		}
		uploadSaving = true;
		try {
			await createNf(uploadFile, uploadFiscalMes, uploadImages.length > 0 ? uploadImages : undefined, Number(uploadSpread));
			toast.success('NF salva');
			uploadOpen = false;
			resetUpload();
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao salvar');
		} finally {
			uploadSaving = false;
		}
	}

	// ---------------------------------------------------------------------------
	// Detail
	// ---------------------------------------------------------------------------

	async function openDetail(nf: NfEntry) {
		detailNf = nf;
		detailSpread = String(nf.spread);
		detailImages = [];
		replacingPdf = false;
		addingImages = false;
		detailOpen = true;
		try {
			detailImages = await getNfImages(nf.id);
		} catch {
			// images may be empty
		}
	}

	async function saveSpread() {
		if (!detailNf || !validSpread(detailSpread)) return;
		const nfId = detailNf.id;
		savingSpread = true;
		try {
			const updated = await patchNfSpread(nfId, Number(detailSpread));
			if (detailNf?.id === nfId) {
				detailNf = updated;
				detailSpread = String(updated.spread);
			}
			toast.success('Spread atualizado e valores em BRL recalculados');
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao atualizar spread');
		} finally {
			savingSpread = false;
		}
	}

	async function refreshDetail() {
		if (!detailNf) return;
		try {
			detailNf = await getNf(detailNf.id);
			detailImages = await getNfImages(detailNf.id);
		} catch {
			// silently fail
		}
	}

	function openPreview(path: string, title: string, fallbackFilename: string) {
		previewPath = path;
		previewTitle = title;
		previewFallback = fallbackFilename;
		previewOpen = true;
	}

	async function downloadPdf(nfId: number) {
		try {
			const { blob, filename } = await downloadBlob(`/nfs/${nfId}/pdf`);
			triggerDownload(blob, filename ?? `nf_${nfId}.pdf`);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao baixar');
		}
	}

	async function downloadImage(nfId: number, imageId: number) {
		try {
			const { blob, filename } = await downloadBlob(`/nfs/${nfId}/images/${imageId}`);
			triggerDownload(blob, filename ?? `nf_${nfId}_img_${imageId}`);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao baixar');
		}
	}

	function previewPdf(nfId: number) {
		openPreview(`/nfs/${nfId}/pdf`, `NF #${nfId} PDF`, `nf_${nfId}.pdf`);
	}

	function previewImage(nfId: number, imageId: number) {
		openPreview(
			`/nfs/${nfId}/images/${imageId}`,
			`Image #${imageId}`,
			`nf_${nfId}_img_${imageId}`
		);
	}

	// ---------------------------------------------------------------------------
	// Detail: Replace PDF
	// ---------------------------------------------------------------------------

	async function handleReplacePdf(files: File[]) {
		if (!detailNf || files.length === 0) return;
		replacingPdf = true;
		try {
			detailNf = await updateNfPdf(detailNf.id, files[0]);
			detailSpread = String(detailNf.spread);
			toast.success('PDF da NF substituído');
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao substituir');
		} finally {
			replacingPdf = false;
		}
	}

	function openReplacePdfPicker() {
		replacePdfInputEl?.click();
	}

	function handleReplacePdfInputChange(e: Event) {
		const target = e.target as HTMLInputElement;
		void handleReplacePdf(Array.from(target.files ?? []));
		target.value = '';
	}

	// ---------------------------------------------------------------------------
	// Detail: Add/Delete Images
	// ---------------------------------------------------------------------------

	async function handleAddImages(files: File[]) {
		if (!detailNf || files.length === 0) return;
		addingImages = true;
		try {
			detailImages = await addNfImages(detailNf.id, files);
			toast.success(`${files.length} imagem(ns) adicionada(s)`);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao enviar');
		} finally {
			addingImages = false;
		}
	}

	async function handleDeleteImage(imageId: number) {
		if (!detailNf) return;
		try {
			await deleteNfImage(detailNf.id, imageId);
			detailImages = detailImages.filter((img) => img.id !== imageId);
			toast.success('Imagem excluída');
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao excluir');
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
			toast.success('Mês fiscal atualizado');
			editingFmId = null;
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao atualizar');
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
			toast.success('NF excluída');
			deleteTarget = null;
			await loadNfs();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao excluir');
		}
	}
</script>

<div class="space-y-6">
	<PageHeader title="Notas Fiscais" description="Notas fiscais de serviço e conversão de USD para BRL.">
		{#snippet actions()}
			<Button onclick={openUpload}>
				<Plus class="h-4 w-4" />
				Enviar NF
			</Button>
		{/snippet}
	</PageHeader>

	<!-- Filters -->
	<div class="flex flex-wrap items-end gap-3">
		<div class="space-y-1">
			<span class="text-xs font-medium text-muted-foreground">Mês fiscal</span>
			<FiscalMonthPicker bind:value={filterMonth} {months} />
		</div>
		{#if !filterMonth}
			<div class="space-y-1">
				<label for="nf-date-from" class="text-xs font-medium text-muted-foreground">De</label>
				<Input id="nf-date-from" type="date" bind:value={filterDateFrom} class="w-40" />
			</div>
			<div class="space-y-1">
				<label for="nf-date-to" class="text-xs font-medium text-muted-foreground">Até</label>
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
				<p class="text-muted-foreground">Nenhuma nota fiscal encontrada.</p>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="rounded-lg border">
			<Table.Table>
				<Table.TableHeader>
					<Table.TableRow>
						{#each [
							{ key: 'nf_date', label: 'Data' },
							{ key: 'company', label: 'Empresa' },
							{ key: 'usd', label: 'USD' },
							{ key: 'rate', label: 'Cotação' },
							{ key: 'spread', label: 'Spread' },
							{ key: 'brl_with_spread', label: 'BRL' },
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
										title="Clique para editar o mês fiscal"
									>
										{formatFiscalMes(nf.fiscal_mes)}
									</button>
								{/if}
							</Table.TableCell>
							<Table.TableCell>
								<div class="flex items-center gap-1">
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => openDetail(nf)} title="Ver detalhes">
										<Eye class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7" onclick={() => downloadPdf(nf.id)} title="Baixar PDF">
										<Download class="h-3.5 w-3.5" />
									</Button>
									<Button variant="ghost" size="icon" class="h-7 w-7 text-destructive-foreground" onclick={() => confirmDelete(nf)} title="Excluir">
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
			<Sheet.SheetTitle>Enviar nota fiscal</Sheet.SheetTitle>
			<Sheet.SheetDescription>Selecione os arquivos, processe e revise os dados antes de salvar.</Sheet.SheetDescription>
			<UploadSteps ready={!!uploadPreview} />
		</Sheet.SheetHeader>
		<div class="min-h-0 flex-1 overflow-y-auto px-6 py-4 space-y-6">
			<UploadFiles ready={!!uploadPreview} count={(uploadFile ? 1 : 0) + uploadImages.length}>
				<!-- PDF drop zone -->
				<div class="space-y-2">
					<span class="text-sm font-medium">PDF da NF</span>
					<FileDropZone
						accept=".pdf,application/pdf"
						loading={uploadPreviewing || uploadSaving}
						bind:file={uploadFile}
						onchange={invalidateUpload}
						label="Arraste o PDF da NF ou clique para escolher"
					/>
				</div>

				<!-- Image attachments -->
				<div class="space-y-2">
					<span class="text-sm font-medium">Imagens anexas (opcional)</span>
					<FileDropZone
						accept="image/*"
						multiple={true}
						bind:files={uploadImages}
						loading={uploadPreviewing || uploadSaving}
						onchange={invalidateUpload}
						label="Arraste as imagens ou clique para escolher"
					/>
				</div>
			</UploadFiles>

			<!-- Preview card -->
			{#if uploadPreview}
				<Card.Root>
					<Card.Header class="pb-3">
						<Card.Title class="text-sm">Dados extraídos</Card.Title>
					</Card.Header>
					<Card.Content>
						<dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
							<dt class="text-muted-foreground">Empresa</dt>
							<dd>{uploadPreview.company ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">USD</dt>
							<dd class="tabular-nums">{formatUsd(uploadPreview.usd)}</dd>
							<dt class="text-muted-foreground">Cotação</dt>
							<dd class="tabular-nums">{formatNumber(uploadPreview.rate, 4)}</dd>
							<dt class="text-muted-foreground"><label for="upload-spread">Spread (%)</label></dt>
							<dd class="tabular-nums">
								<Input id="upload-spread" type="number" min="0" max="100" step="any" bind:value={uploadSpread} disabled={uploadSaving} aria-describedby="upload-spread-help" />
								{#if uploadPreview.spread_was_default}
									<Badge variant="outline" class="ml-1 text-[10px] px-1">padrão</Badge>
								{/if}
							</dd>
							{#if uploadPreview.brl}
								<dt class="text-muted-foreground">BRL (sem spread)</dt>
								<dd class="tabular-nums">{formatBrl(uploadPreview.brl.brl_no_spread)}</dd>
								<dt class="text-muted-foreground">BRL (com spread)</dt>
								<dd class="tabular-nums font-medium">{formatBrl(uploadBrl)}</dd>
							{/if}
							<dt class="text-muted-foreground">Data</dt>
							<dd>{formatDateBr(uploadPreview.nf_date)}</dd>
							<dt class="text-muted-foreground">Código de verificação</dt>
							<dd class="font-mono text-xs">{uploadPreview.verification_code ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Forma de pagamento</dt>
							<dd>{uploadPreview.payment_via ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Origem</dt>
							<dd>
								<Badge variant="secondary" class="text-xs">{uploadPreview.source}</Badge>
							</dd>
						</dl>
						<p id="upload-spread-help" class="mt-3 text-xs text-muted-foreground">Spread usado no cálculo (0–100%). Para 0,3%, digite 0.3. O PDF original é preservado.</p>
					</Card.Content>
				</Card.Root>
			{/if}

			<!-- Fiscal month picker -->
			{#if uploadPreview}
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
			canProcess={!!uploadFile}
			canSave={!!uploadFiscalMes && !!uploadPreview?.brl && uploadSpreadValid}
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
			<Sheet.SheetTitle>Detalhes da NF</Sheet.SheetTitle>
			{#if detailNf}
				<Sheet.SheetDescription>ID: {detailNf.id} &middot; {formatFiscalMes(detailNf.fiscal_mes)}</Sheet.SheetDescription>
			{/if}
		</Sheet.SheetHeader>
		{#if detailNf}
			<div class="flex-1 overflow-y-auto px-6 py-4 space-y-5">
				<!-- NF Data Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center justify-between">
							<div class="flex items-center gap-2">
								<FileText class="h-4 w-4 text-muted-foreground" />
								<Card.Title class="text-sm">Nota Fiscal</Card.Title>
								<Button
									variant="ghost"
									size="icon"
									class="h-7 w-7"
									title="Substituir PDF da NF"
									onclick={openReplacePdfPicker}
									disabled={replacingPdf || savingSpread}
								>
									{#if replacingPdf}
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
									onclick={() => previewPdf(detailNf!.id)}
									title="Ver PDF"
								>
									<Eye class="h-3.5 w-3.5" />
									Visualizar
								</Button>
								<Button
									variant="outline"
									size="sm"
									class="h-7 text-xs"
									onclick={() => downloadPdf(detailNf!.id)}
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
							<dt class="text-muted-foreground">Empresa</dt>
							<dd>{detailNf.company ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">USD</dt>
							<dd class="tabular-nums font-medium">{formatUsd(detailNf.usd)}</dd>
							<dt class="text-muted-foreground">Cotação</dt>
							<dd class="tabular-nums">{formatNumber(detailNf.rate, 4)}</dd>
							<dt class="text-muted-foreground">Spread</dt>
							<dd class="tabular-nums">{formatPercent(detailNf.spread)}</dd>
							<dt class="text-muted-foreground">BRL (sem spread)</dt>
							<dd class="tabular-nums">{formatBrl(detailNf.brl_no_spread)}</dd>
							<dt class="text-muted-foreground">BRL (com spread)</dt>
							<dd class="tabular-nums font-medium">{formatBrl(detailNf.brl_with_spread)}</dd>
							<dt class="text-muted-foreground">Data</dt>
							<dd>{formatDateBr(detailNf.nf_date)}</dd>
							<dt class="text-muted-foreground">Código de verificação</dt>
							<dd class="font-mono text-xs">{detailNf.verification_code ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Forma de pagamento</dt>
							<dd>{detailNf.payment_via ?? '\u2014'}</dd>
							<dt class="text-muted-foreground">Mês fiscal</dt>
							<dd>{formatFiscalMes(detailNf.fiscal_mes)}</dd>
							<dt class="text-muted-foreground">Criado em</dt>
							<dd class="text-xs">{detailNf.created_at}</dd>
						</dl>
						<form class="space-y-2 border-t border-border pt-4" onsubmit={(event) => { event.preventDefault(); saveSpread(); }}>
							<label for="detail-spread" class="text-sm font-medium">Spread do cálculo (%)</label>
							<div class="flex items-center gap-2">
								<Input id="detail-spread" type="number" min="0" max="100" step="any" required bind:value={detailSpread} disabled={savingSpread || replacingPdf} aria-describedby="detail-spread-help" />
								<Button type="submit" disabled={savingSpread || replacingPdf || !validSpread(detailSpread) || Number(detailSpread) === detailNf.spread}>
									{savingSpread ? 'Salvando…' : 'Salvar spread'}
									</Button>
								</div>
							<p id="detail-spread-help" class="text-xs text-muted-foreground">Recalcula os valores em BRL. O PDF original é preservado. Para 0,3%, digite 0.3.</p>
						</form>
					</Card.Content>
					<input
						bind:this={replacePdfInputEl}
						type="file"
						accept=".pdf,application/pdf"
						class="sr-only"
						onchange={handleReplacePdfInputChange}
					/>
				</Card.Root>

				<!-- Images Card -->
				<Card.Root>
					<Card.Header class="pb-3">
						<div class="flex items-center gap-2">
							<ImageIcon class="h-4 w-4 text-muted-foreground" />
							<Card.Title class="text-sm">Attachments ({detailImages.length})</Card.Title>
						</div>
					</Card.Header>
					<Card.Content class="space-y-4">
						{#if detailImages.length > 0}
							<div class="grid grid-cols-1 gap-2">
								{#each detailImages as img (img.id)}
									<div class="flex items-center justify-between rounded-md border border-border px-3 py-2">
										<button
											class="text-sm text-muted-foreground hover:text-foreground transition-colors truncate flex-1 text-left"
											onclick={() => previewImage(detailNf!.id, img.id)}
										>
											Image #{img.id}
										</button>
										<div class="flex items-center gap-1 ml-2 shrink-0">
											<Button
												variant="ghost"
												size="icon"
												class="h-7 w-7"
												onclick={() => previewImage(detailNf!.id, img.id)}
												title="Visualizar"
											>
												<Eye class="h-3.5 w-3.5" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												class="h-7 w-7"
												onclick={() => downloadImage(detailNf!.id, img.id)}
												title="Baixar"
											>
												<Download class="h-3.5 w-3.5" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												class="h-7 w-7 text-destructive-foreground"
												onclick={() => handleDeleteImage(img.id)}
												title="Excluir"
											>
												<Trash2 class="h-3.5 w-3.5" />
											</Button>
										</div>
									</div>
								{/each}
							</div>
						{:else}
							<p class="text-sm text-muted-foreground">Nenhuma imagem anexada.</p>
						{/if}

						<Separator />

						<div class="space-y-2">
							<span class="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
								<Plus class="h-3 w-3" />
								Add Images
							</span>
							<FileDropZone
								accept="image/*"
								multiple={true}
								loading={addingImages}
								onchange={handleAddImages}
								label="Drop images here to add"
							/>
						</div>
					</Card.Content>
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
	title="Excluir nota fiscal"
	description="A nota fiscal, o PDF e as imagens anexas serão excluídos."
	onconfirm={handleDelete}
/>
