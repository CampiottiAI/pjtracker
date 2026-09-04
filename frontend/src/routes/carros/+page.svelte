<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import {
		ApiError,
		formatApiErrorMessage,
		listCars,
		createCar,
		patchCar,
		deleteCar,
		listCarMaintenance,
		maintenanceParsePreview,
		createMaintenance,
		getMaintenance,
		deleteMaintenance,
		addMaintenanceAttachment
	} from '$lib/api/client.js';
	import type {
		Car,
		MaintenanceExtracted,
		MaintenanceRecord,
		MaintenanceVeiculo
	} from '$lib/api/types.js';
	import { formatBrl } from '$lib/utils/format.js';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import FileDropZone from '$lib/components/FileDropZone.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import FilePreviewDialog from '$lib/components/FilePreviewDialog.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as Sheet from '$lib/components/ui/sheet/index.js';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import {
		Plus,
		Trash2,
		Eye,
		Loader2,
		ArrowLeft,
		FileText,
		Video,
		Image as ImageIcon,
		Settings2,
		Paperclip
	} from 'lucide-svelte';

	let cars = $state<Car[]>([]);
	let selectedCarId = $state('');
	let records = $state<MaintenanceRecord[]>([]);
	let loading = $state(true);
	let loadingHistory = $state(false);

	let selectedRecord = $state<MaintenanceRecord | null>(null);
	let detailTab = $state('documento');

	// Manage cars sheet
	let manageOpen = $state(false);
	let newCarName = $state('');
	let newCarPlaca = $state('');
	let newCarModelo = $state('');
	let newCarId = $state('');
	let savingCar = $state(false);

	// Upload / preview
	let uploadFile = $state<File | null>(null);
	let uploadPreviewing = $state(false);
	let uploadSaving = $state(false);
	let editExtracted = $state<MaintenanceExtracted | null>(null);

	// Attachments
	let attaching = $state(false);
	let attachInputEl: HTMLInputElement | undefined = $state();

	// Preview dialog
	let previewOpen = $state(false);
	let previewPath = $state<string | null>(null);
	let previewTitle = $state('Preview');
	let previewFallback = $state('file');

	// Delete dialogs
	let deleteRecordOpen = $state(false);
	let deleteCarOpen = $state(false);
	let deleteCarTarget = $state<Car | null>(null);

	const selectedCar = $derived(cars.find((c) => c.id === selectedCarId) ?? null);

	onMount(async () => {
		await loadCars();
	});

	async function loadCars(preferId?: string) {
		loading = true;
		try {
			const res = await listCars();
			cars = res.items;
			const next =
				preferId && cars.some((c) => c.id === preferId)
					? preferId
					: selectedCarId && cars.some((c) => c.id === selectedCarId)
						? selectedCarId
						: (cars[0]?.id ?? '');
			selectedCarId = next;
			if (selectedCarId) await loadHistory();
			else records = [];
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar carros');
		} finally {
			loading = false;
		}
	}

	async function loadHistory() {
		if (!selectedCarId) {
			records = [];
			return;
		}
		loadingHistory = true;
		try {
			const res = await listCarMaintenance(selectedCarId);
			records = res.items;
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao carregar histórico'
			);
		} finally {
			loadingHistory = false;
		}
	}

	async function onCarChange(id: string) {
		selectedCarId = id;
		selectedRecord = null;
		clearUpload();
		await loadHistory();
	}

	function clearUpload() {
		uploadFile = null;
		editExtracted = null;
	}

	function emptyVeiculo(): MaintenanceVeiculo {
		return { placa: null, modelo: null, cor: null, ano: null, km: null, chassi: null };
	}

	async function handleFileSelected(files: File[]) {
		const file = files[0];
		if (!file || !selectedCarId) return;
		uploadFile = file;
		uploadPreviewing = true;
		editExtracted = null;
		try {
			const preview = await maintenanceParsePreview(selectedCarId, file);
			editExtracted = {
				...preview.extracted,
				veiculo: { ...emptyVeiculo(), ...(preview.extracted.veiculo ?? {}) },
				itens: preview.extracted.itens ?? []
			};
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha na extração'
			);
			uploadFile = null;
		} finally {
			uploadPreviewing = false;
		}
	}

	async function handleSave() {
		if (!selectedCarId || !uploadFile || !editExtracted) return;
		uploadSaving = true;
		try {
			const record = await createMaintenance(selectedCarId, uploadFile, editExtracted);
			if (record.warning) {
				toast.warning(`Salvo, mas análise falhou: ${record.warning}`);
			} else {
				toast.success('Orçamento salvo');
			}
			clearUpload();
			await loadHistory();
			selectedRecord = record;
			detailTab = 'analise';
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao salvar');
		} finally {
			uploadSaving = false;
		}
	}

	async function openRecord(id: string) {
		try {
			selectedRecord = await getMaintenance(id);
			detailTab = 'documento';
		} catch (e) {
			toast.error(
				e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao abrir registro'
			);
		}
	}

	async function confirmDeleteRecord() {
		if (!selectedRecord) return;
		try {
			await deleteMaintenance(selectedRecord.id);
			toast.success('Registro excluído');
			selectedRecord = null;
			await loadHistory();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao excluir');
		} finally {
			deleteRecordOpen = false;
		}
	}

	async function handleAddCar() {
		const name = newCarName.trim();
		if (!name) {
			toast.error('Nome é obrigatório');
			return;
		}
		savingCar = true;
		try {
			const car = await createCar({
				name,
				id: newCarId.trim() || undefined,
				placa: newCarPlaca.trim() || undefined,
				modelo: newCarModelo.trim() || undefined
			});
			toast.success('Carro adicionado');
			newCarName = '';
			newCarPlaca = '';
			newCarModelo = '';
			newCarId = '';
			await loadCars(car.id);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao adicionar');
		} finally {
			savingCar = false;
		}
	}

	async function handleSaveCar(car: Car) {
		try {
			await patchCar(car.id, {
				name: car.name,
				placa: car.placa ?? '',
				modelo: car.modelo ?? ''
			});
			toast.success('Carro atualizado');
			await loadCars(car.id);
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao salvar');
		}
	}

	async function confirmDeleteCar() {
		if (!deleteCarTarget) return;
		try {
			await deleteCar(deleteCarTarget.id);
			toast.success('Carro removido');
			if (selectedCarId === deleteCarTarget.id) selectedCarId = '';
			await loadCars();
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao remover');
		} finally {
			deleteCarOpen = false;
			deleteCarTarget = null;
		}
	}

	function openSourcePreview(record: MaintenanceRecord) {
		previewPath = `/cars/maintenance/${record.id}/source`;
		previewTitle = record.source.filename;
		previewFallback = record.source.filename;
		previewOpen = true;
	}

	function openAttachmentPreview(recordId: string, attId: string, filename: string) {
		previewPath = `/cars/maintenance/${recordId}/attachments/${attId}`;
		previewTitle = filename;
		previewFallback = filename;
		previewOpen = true;
	}

	async function handleAttach(files: FileList | null) {
		if (!selectedRecord || !files?.length) return;
		attaching = true;
		try {
			for (const file of Array.from(files)) {
				await addMaintenanceAttachment(selectedRecord.id, file);
			}
			selectedRecord = await getMaintenance(selectedRecord.id);
			toast.success('Anexo(s) adicionados');
		} catch (e) {
			toast.error(e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Falha ao anexar');
		} finally {
			attaching = false;
			if (attachInputEl) attachInputEl.value = '';
		}
	}

	function recordLabel(r: MaintenanceRecord): string {
		const ex = r.extracted ?? {};
		const parts = [
			ex.data || '—',
			ex.veiculo?.km != null ? `${ex.veiculo.km} km` : null,
			ex.total != null ? formatBrl(ex.total) : null,
			ex.oficina || null
		].filter(Boolean);
		return parts.join(' · ');
	}

	function isVideoMime(mime: string): boolean {
		return mime.startsWith('video/');
	}

	function isImageMime(mime: string): boolean {
		return mime.startsWith('image/');
	}

	function updateVeiculoField<K extends keyof MaintenanceVeiculo>(
		key: K,
		value: MaintenanceVeiculo[K]
	) {
		if (!editExtracted) return;
		editExtracted = {
			...editExtracted,
			veiculo: { ...emptyVeiculo(), ...(editExtracted.veiculo ?? {}), [key]: value }
		};
	}
</script>

<PageHeader title="Carros" description="Orçamentos de manutenção, histórico por carro e anexos.">
	{#snippet actions()}
		{#if !selectedRecord}
			<Button variant="outline" size="sm" onclick={() => (manageOpen = true)}>
				<Settings2 class="h-4 w-4" />
				Gerenciar carros
			</Button>
		{/if}
	{/snippet}
</PageHeader>

{#if loading}
	<div class="flex items-center justify-center py-20 text-muted-foreground">
		<Loader2 class="h-6 w-6 animate-spin" />
	</div>
{:else if selectedRecord}
	<!-- Detail view -->
	<div class="mb-4 flex items-center gap-2">
		<Button
			variant="ghost"
			size="sm"
			onclick={() => {
				selectedRecord = null;
			}}
		>
			<ArrowLeft class="h-4 w-4" />
			Voltar
		</Button>
		<span class="text-sm text-muted-foreground">{recordLabel(selectedRecord)}</span>
		<div class="flex-1"></div>
		<Button variant="destructive" size="sm" onclick={() => (deleteRecordOpen = true)}>
			<Trash2 class="h-4 w-4" />
			Excluir
		</Button>
	</div>

	<Tabs.Root bind:value={detailTab}>
		<Tabs.List>
			<Tabs.Trigger value="documento">Documento</Tabs.Trigger>
			<Tabs.Trigger value="analise">Análise</Tabs.Trigger>
			<Tabs.Trigger value="anexos">Anexos</Tabs.Trigger>
		</Tabs.List>

		<Tabs.Content value="documento" class="mt-4 space-y-4">
			<div class="flex gap-2">
				<Button variant="outline" size="sm" onclick={() => openSourcePreview(selectedRecord!)}>
					<Eye class="h-4 w-4" />
					Ver arquivo
				</Button>
			</div>
			{@const ex = selectedRecord.extracted}
			{@const v = ex.veiculo ?? {}}
			<div class="grid gap-4 sm:grid-cols-2">
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Orçamento</Card.Title>
					</Card.Header>
					<Card.Content class="space-y-2 text-sm">
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Oficina</span>
							<span>{ex.oficina || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Data</span>
							<span>{ex.data || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Cliente</span>
							<span>{ex.cliente || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Consultor</span>
							<span>{ex.consultor || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Total</span>
							<span class="font-medium">{formatBrl(ex.total)}</span>
						</div>
						{#if ex.observacoes}
							<p class="pt-2 text-muted-foreground">{ex.observacoes}</p>
						{/if}
					</Card.Content>
				</Card.Root>
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Veículo</Card.Title>
					</Card.Header>
					<Card.Content class="space-y-2 text-sm">
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Placa</span>
							<span>{v.placa || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Modelo</span>
							<span>{v.modelo || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Cor</span>
							<span>{v.cor || '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Ano</span>
							<span>{v.ano ?? '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Km</span>
							<span>{v.km ?? '—'}</span>
						</div>
						<div class="flex justify-between gap-2">
							<span class="text-muted-foreground">Chassi</span>
							<span class="truncate">{v.chassi || '—'}</span>
						</div>
					</Card.Content>
				</Card.Root>
			</div>
			{#if ex.itens?.length}
				<Card.Root>
					<Card.Header>
						<Card.Title class="text-base">Itens</Card.Title>
					</Card.Header>
					<Card.Content>
						<div class="overflow-x-auto">
							<Table.Table>
								<Table.TableHeader>
									<Table.TableRow>
										<Table.TableHead>Código</Table.TableHead>
										<Table.TableHead>Descrição</Table.TableHead>
										<Table.TableHead class="text-right">Qtd</Table.TableHead>
										<Table.TableHead class="text-right">Unit.</Table.TableHead>
										<Table.TableHead class="text-right">Total</Table.TableHead>
									</Table.TableRow>
								</Table.TableHeader>
								<Table.TableBody>
									{#each ex.itens as item}
										<Table.TableRow>
											<Table.TableCell class="text-muted-foreground">{item.codigo || '—'}</Table.TableCell>
											<Table.TableCell>{item.descricao}</Table.TableCell>
											<Table.TableCell class="text-right">{item.quantidade ?? '—'}</Table.TableCell>
											<Table.TableCell class="text-right">{formatBrl(item.valor_unitario)}</Table.TableCell>
											<Table.TableCell class="text-right">{formatBrl(item.valor_total)}</Table.TableCell>
										</Table.TableRow>
									{/each}
								</Table.TableBody>
							</Table.Table>
						</div>
					</Card.Content>
				</Card.Root>
			{/if}
		</Tabs.Content>

		<Tabs.Content value="analise" class="mt-4">
			{#if selectedRecord.analysis}
				<div class="space-y-4">
					<Card.Root>
						<Card.Header>
							<Card.Title class="text-base">Resumo</Card.Title>
						</Card.Header>
						<Card.Content class="whitespace-pre-wrap text-sm">
							{selectedRecord.analysis.resumo}
						</Card.Content>
					</Card.Root>
					{#if selectedRecord.analysis.mudancas}
						<Card.Root>
							<Card.Header>
								<Card.Title class="text-base">Mudanças vs visita anterior</Card.Title>
							</Card.Header>
							<Card.Content class="whitespace-pre-wrap text-sm">
								{selectedRecord.analysis.mudancas}
							</Card.Content>
						</Card.Root>
					{/if}
					<Card.Root>
						<Card.Header>
							<Card.Title class="text-base">Motivo geral</Card.Title>
						</Card.Header>
						<Card.Content class="whitespace-pre-wrap text-sm">
							{selectedRecord.analysis.motivo_geral}
						</Card.Content>
					</Card.Root>
				</div>
			{:else}
				<p class="text-sm text-muted-foreground">Nenhuma análise disponível para este registro.</p>
			{/if}
		</Tabs.Content>

		<Tabs.Content value="anexos" class="mt-4 space-y-4">
			<div class="flex flex-wrap items-center gap-2">
				<input
					bind:this={attachInputEl}
					type="file"
					class="hidden"
					accept=".jpg,.jpeg,.png,.webp,.pdf,.mp4,.m4v,.mov,.webm,.avi,.mkv,.mpeg,.mpg"
					multiple
					onchange={(e) => handleAttach((e.currentTarget as HTMLInputElement).files)}
				/>
				<Button
					size="sm"
					disabled={attaching}
					onclick={() => attachInputEl?.click()}
				>
					{#if attaching}
						<Loader2 class="h-4 w-4 animate-spin" />
					{:else}
						<Paperclip class="h-4 w-4" />
					{/if}
					Anexar arquivo
				</Button>
			</div>

			<div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
				<button
					type="button"
					class="flex flex-col items-center gap-2 rounded-lg border border-border bg-card p-4 text-left hover:bg-accent/40"
					onclick={() => openSourcePreview(selectedRecord!)}
				>
					{#if isImageMime(selectedRecord.source.mime_type)}
						<ImageIcon class="h-10 w-10 text-muted-foreground" />
					{:else if isVideoMime(selectedRecord.source.mime_type)}
						<Video class="h-10 w-10 text-muted-foreground" />
					{:else}
						<FileText class="h-10 w-10 text-muted-foreground" />
					{/if}
					<span class="w-full truncate text-center text-xs">{selectedRecord.source.filename}</span>
					<Badge variant="secondary" class="text-[10px]">Fonte</Badge>
				</button>
				{#each selectedRecord.attachments ?? [] as att}
					<button
						type="button"
						class="flex flex-col items-center gap-2 rounded-lg border border-border bg-card p-4 text-left hover:bg-accent/40"
						onclick={() => openAttachmentPreview(selectedRecord!.id, att.id, att.filename)}
					>
						{#if isImageMime(att.mime_type)}
							<ImageIcon class="h-10 w-10 text-muted-foreground" />
						{:else if isVideoMime(att.mime_type)}
							<Video class="h-10 w-10 text-muted-foreground" />
						{:else}
							<FileText class="h-10 w-10 text-muted-foreground" />
						{/if}
						<span class="w-full truncate text-center text-xs">{att.filename}</span>
					</button>
				{/each}
			</div>
		</Tabs.Content>
	</Tabs.Root>
{:else}
	<!-- List / upload view -->
	{#if cars.length === 0}
		<Card.Root>
			<Card.Content class="flex flex-col items-center gap-3 py-12 text-center">
				<p class="text-sm text-muted-foreground">
					Adicione pelo menos um carro para registrar orçamentos.
				</p>
				<Button onclick={() => (manageOpen = true)}>
					<Plus class="h-4 w-4" />
					Adicionar carro
				</Button>
			</Card.Content>
		</Card.Root>
	{:else}
		<div class="mb-6 flex flex-wrap items-center gap-3">
			<label class="text-sm text-muted-foreground" for="car-select">Carro</label>
			<select
				id="car-select"
				class="h-9 rounded-md border border-input bg-background px-3 text-sm"
				value={selectedCarId}
				onchange={(e) => onCarChange((e.currentTarget as HTMLSelectElement).value)}
			>
				{#each cars as car}
					<option value={car.id}>{car.label ?? car.name}</option>
				{/each}
			</select>
		</div>

		<div class="grid gap-6 lg:grid-cols-2">
			<Card.Root>
				<Card.Header>
					<Card.Title class="text-base">Novo orçamento</Card.Title>
					<Card.Description>
						Envie imagem ou PDF. Revise os dados antes de salvar.
					</Card.Description>
				</Card.Header>
				<Card.Content class="space-y-4">
					<FileDropZone
						accept=".jpg,.jpeg,.png,.webp,.pdf"
						loading={uploadPreviewing}
						label="Solte o orçamento ou clique para escolher"
						onchange={handleFileSelected}
					/>

					{#if editExtracted && uploadFile}
						<div class="space-y-3 rounded-lg border border-border p-3">
							<p class="text-xs text-muted-foreground">
								Arquivo: {uploadFile.name}
							</p>
							<div class="grid gap-2 sm:grid-cols-2">
								<div>
									<label class="text-xs text-muted-foreground" for="ex-oficina">Oficina</label>
									<Input
										id="ex-oficina"
										value={editExtracted.oficina ?? ''}
										oninput={(e) =>
											(editExtracted = {
												...editExtracted!,
												oficina: (e.currentTarget as HTMLInputElement).value
											})}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-data">Data</label>
									<Input
										id="ex-data"
										value={editExtracted.data ?? ''}
										oninput={(e) =>
											(editExtracted = {
												...editExtracted!,
												data: (e.currentTarget as HTMLInputElement).value
											})}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-cliente">Cliente</label>
									<Input
										id="ex-cliente"
										value={editExtracted.cliente ?? ''}
										oninput={(e) =>
											(editExtracted = {
												...editExtracted!,
												cliente: (e.currentTarget as HTMLInputElement).value
											})}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-consultor">Consultor</label>
									<Input
										id="ex-consultor"
										value={editExtracted.consultor ?? ''}
										oninput={(e) =>
											(editExtracted = {
												...editExtracted!,
												consultor: (e.currentTarget as HTMLInputElement).value
											})}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-placa">Placa</label>
									<Input
										id="ex-placa"
										value={editExtracted.veiculo?.placa ?? ''}
										oninput={(e) =>
											updateVeiculoField('placa', (e.currentTarget as HTMLInputElement).value)}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-modelo">Modelo</label>
									<Input
										id="ex-modelo"
										value={editExtracted.veiculo?.modelo ?? ''}
										oninput={(e) =>
											updateVeiculoField('modelo', (e.currentTarget as HTMLInputElement).value)}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-cor">Cor</label>
									<Input
										id="ex-cor"
										value={editExtracted.veiculo?.cor ?? ''}
										oninput={(e) =>
											updateVeiculoField('cor', (e.currentTarget as HTMLInputElement).value)}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-ano">Ano</label>
									<Input
										id="ex-ano"
										type="number"
										value={editExtracted.veiculo?.ano != null ? String(editExtracted.veiculo.ano) : ''}
										oninput={(e) => {
											const raw = (e.currentTarget as HTMLInputElement).value;
											updateVeiculoField('ano', raw ? Number(raw) : null);
										}}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-km">Km</label>
									<Input
										id="ex-km"
										type="number"
										value={editExtracted.veiculo?.km != null ? String(editExtracted.veiculo.km) : ''}
										oninput={(e) => {
											const raw = (e.currentTarget as HTMLInputElement).value;
											updateVeiculoField('km', raw ? Number(raw) : null);
										}}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-chassi">Chassi</label>
									<Input
										id="ex-chassi"
										value={editExtracted.veiculo?.chassi ?? ''}
										oninput={(e) =>
											updateVeiculoField('chassi', (e.currentTarget as HTMLInputElement).value)}
									/>
								</div>
								<div>
									<label class="text-xs text-muted-foreground" for="ex-total">Total</label>
									<Input
										id="ex-total"
										type="number"
										step="0.01"
										value={editExtracted.total != null ? String(editExtracted.total) : ''}
										oninput={(e) => {
											const raw = (e.currentTarget as HTMLInputElement).value;
											editExtracted = {
												...editExtracted!,
												total: raw ? Number(raw) : null
											};
										}}
									/>
								</div>
							</div>
							<div>
								<label class="text-xs text-muted-foreground" for="ex-obs">Observações</label>
								<Input
									id="ex-obs"
									value={editExtracted.observacoes ?? ''}
									oninput={(e) =>
										(editExtracted = {
											...editExtracted!,
											observacoes: (e.currentTarget as HTMLInputElement).value
										})}
								/>
							</div>

							{#if editExtracted.itens?.length}
								<div class="overflow-x-auto rounded-md border border-border">
									<Table.Table>
										<Table.TableHeader>
											<Table.TableRow>
												<Table.TableHead>Descrição</Table.TableHead>
												<Table.TableHead class="text-right">Total</Table.TableHead>
											</Table.TableRow>
										</Table.TableHeader>
										<Table.TableBody>
											{#each editExtracted.itens as item}
												<Table.TableRow>
													<Table.TableCell class="text-sm">{item.descricao}</Table.TableCell>
													<Table.TableCell class="text-right text-sm"
														>{formatBrl(item.valor_total)}</Table.TableCell
													>
												</Table.TableRow>
											{/each}
										</Table.TableBody>
									</Table.Table>
								</div>
								<p class="text-xs text-muted-foreground">Itens são somente leitura.</p>
							{/if}

							<div class="flex gap-2">
								<Button disabled={uploadSaving} onclick={handleSave}>
									{#if uploadSaving}
										<Loader2 class="h-4 w-4 animate-spin" />
									{/if}
									Salvar e analisar
								</Button>
								<Button variant="outline" disabled={uploadSaving} onclick={clearUpload}>
									Cancelar
								</Button>
							</div>
						</div>
					{/if}
				</Card.Content>
			</Card.Root>

			<Card.Root>
				<Card.Header>
					<Card.Title class="text-base">Histórico</Card.Title>
					<Card.Description>
						{#if selectedCar}
							Visitas de {selectedCar.label ?? selectedCar.name}
						{/if}
					</Card.Description>
				</Card.Header>
				<Card.Content>
					{#if loadingHistory}
						<div class="flex justify-center py-8">
							<Loader2 class="h-5 w-5 animate-spin text-muted-foreground" />
						</div>
					{:else if records.length === 0}
						<p class="py-6 text-center text-sm text-muted-foreground">
							Nenhum orçamento ainda.
						</p>
					{:else}
						<ul class="divide-y divide-border">
							{#each records as r}
								<li>
									<button
										type="button"
										class="flex w-full items-center justify-between gap-2 px-1 py-3 text-left text-sm hover:bg-accent/40"
										onclick={() => openRecord(r.id)}
									>
										<span class="truncate">{recordLabel(r)}</span>
										<Eye class="h-4 w-4 shrink-0 text-muted-foreground" />
									</button>
								</li>
							{/each}
						</ul>
					{/if}
				</Card.Content>
			</Card.Root>
		</div>
	{/if}
{/if}

<!-- Manage cars sheet -->
<Sheet.Root bind:open={manageOpen}>
	<Sheet.Content class="overflow-y-auto sm:max-w-md">
		<Sheet.Header>
			<Sheet.Title>Carros</Sheet.Title>
			<Sheet.Description>Cadastre e edite os veículos da casa.</Sheet.Description>
		</Sheet.Header>

		<div class="mt-4 space-y-6">
			{#each cars as car, i}
				<div class="space-y-2 rounded-lg border border-border p-3">
					<div>
						<label class="text-xs text-muted-foreground" for={`car-name-${car.id}`}>Nome</label>
						<Input
							id={`car-name-${car.id}`}
							value={car.name}
							oninput={(e) => {
								const next = [...cars];
								next[i] = { ...car, name: (e.currentTarget as HTMLInputElement).value };
								cars = next;
							}}
						/>
					</div>
					<div class="grid grid-cols-2 gap-2">
						<div>
							<label class="text-xs text-muted-foreground" for={`car-placa-${car.id}`}>Placa</label>
							<Input
								id={`car-placa-${car.id}`}
								value={car.placa ?? ''}
								oninput={(e) => {
									const next = [...cars];
									next[i] = { ...car, placa: (e.currentTarget as HTMLInputElement).value };
									cars = next;
								}}
							/>
						</div>
						<div>
							<label class="text-xs text-muted-foreground" for={`car-modelo-${car.id}`}
								>Modelo</label
							>
							<Input
								id={`car-modelo-${car.id}`}
								value={car.modelo ?? ''}
								oninput={(e) => {
									const next = [...cars];
									next[i] = { ...car, modelo: (e.currentTarget as HTMLInputElement).value };
									cars = next;
								}}
							/>
						</div>
					</div>
					<div class="flex gap-2">
						<Button size="sm" onclick={() => handleSaveCar(car)}>Salvar</Button>
						<Button
							size="sm"
							variant="destructive"
							disabled={cars.length <= 1}
							onclick={() => {
								deleteCarTarget = car;
								deleteCarOpen = true;
							}}
						>
							Remover
						</Button>
					</div>
					<p class="text-[10px] text-muted-foreground">id: {car.id}</p>
				</div>
			{/each}

			<div class="space-y-2 rounded-lg border border-dashed border-border p-3">
				<p class="text-sm font-medium">Novo carro</p>
				<Input placeholder="Nome" bind:value={newCarName} />
				<div class="grid grid-cols-2 gap-2">
					<Input placeholder="Placa" bind:value={newCarPlaca} />
					<Input placeholder="Modelo" bind:value={newCarModelo} />
				</div>
				<Input placeholder="ID (opcional)" bind:value={newCarId} />
				<Button size="sm" disabled={savingCar} onclick={handleAddCar}>
					{#if savingCar}
						<Loader2 class="h-4 w-4 animate-spin" />
					{:else}
						<Plus class="h-4 w-4" />
					{/if}
					Adicionar
				</Button>
			</div>
		</div>
	</Sheet.Content>
</Sheet.Root>

<ConfirmDialog
	bind:open={deleteRecordOpen}
	title="Excluir registro?"
	description="O orçamento e todos os anexos serão removidos permanentemente."
	confirmLabel="Excluir"
	onconfirm={confirmDeleteRecord}
/>

<ConfirmDialog
	bind:open={deleteCarOpen}
	title="Remover carro?"
	description="Os orçamentos deste carro não serão apagados automaticamente."
	confirmLabel="Remover"
	onconfirm={confirmDeleteCar}
/>

<FilePreviewDialog
	bind:open={previewOpen}
	bind:path={previewPath}
	title={previewTitle}
	fallbackFilename={previewFallback}
/>
