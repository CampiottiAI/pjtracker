<script lang="ts">
	import { cn } from '$lib/utils.js';
	import { Upload, FileCheck, Loader2 } from 'lucide-svelte';

	let {
		accept = '.pdf',
		multiple = false,
		loading = false,
		file = $bindable<File | null>(null),
		files = $bindable<File[]>([]),
		label = 'Arraste um arquivo ou clique para escolher',
		onchange
	}: {
		accept?: string;
		multiple?: boolean;
		loading?: boolean;
		file?: File | null;
		files?: File[];
		label?: string;
		onchange?: (files: File[]) => void;
	} = $props();

	let dragover = $state(false);
	let inputEl: HTMLInputElement | undefined = $state();

	function handleFiles(fileList: FileList | null) {
		if (loading || !fileList || fileList.length === 0) return;
		const arr = Array.from(fileList);
		if (multiple) {
			files = arr;
		} else {
			file = arr[0];
			files = arr.slice(0, 1);
		}
		onchange?.(multiple ? arr : arr.slice(0, 1));
	}

	function handleDrop(e: DragEvent) {
		e.preventDefault();
		dragover = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		dragover = true;
	}

	function handleDragLeave() {
		dragover = false;
	}

	function handleInput(e: Event) {
		const target = e.target as HTMLInputElement;
		handleFiles(target.files);
		target.value = '';
	}

	const hasFile = $derived(multiple ? files.length > 0 : file !== null);
	const displayName = $derived(
		multiple ? files.map((f) => f.name).join(', ') : (file?.name ?? '')
	);
</script>

<button
	type="button"
	class={cn(
		'relative flex w-full flex-col items-center justify-center rounded-lg border border-dashed p-5 text-center transition-colors cursor-pointer',
		dragover
			? 'border-primary bg-primary/5'
			: hasFile
				? 'border-border bg-muted/25'
				: 'border-border hover:border-muted-foreground/50 hover:bg-accent/30'
	)}
	ondrop={handleDrop}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	onclick={() => inputEl?.click()}
	disabled={loading}
>
	{#if loading}
		<Loader2 class="h-6 w-6 text-muted-foreground animate-spin mb-2" />
		<span class="text-sm text-muted-foreground">Processando…</span>
	{:else if hasFile}
		<FileCheck class="h-6 w-6 text-muted-foreground mb-2" />
		<span class="text-sm text-foreground font-medium truncate max-w-full">{displayName}</span>
		<span class="text-xs text-muted-foreground mt-1">Clique ou arraste para substituir</span>
	{:else}
		<Upload class="h-6 w-6 text-muted-foreground mb-2" />
		<span class="text-sm text-muted-foreground">{label}</span>
	{/if}
	<input
		bind:this={inputEl}
		type="file"
		{accept}
		{multiple}
		class="sr-only"
		onchange={handleInput}
	/>
</button>
