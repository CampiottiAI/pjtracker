<script lang="ts">
	import { cn } from '$lib/utils.js';
	import { Upload, FileCheck, Loader2 } from 'lucide-svelte';

	let {
		accept = '.pdf',
		multiple = false,
		loading = false,
		file = $bindable<File | null>(null),
		files = $bindable<File[]>([]),
		label = 'Drop file here or click to browse',
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
		if (!fileList || fileList.length === 0) return;
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
	}

	const hasFile = $derived(file !== null || files.length > 0);
	const displayName = $derived(
		multiple ? files.map((f) => f.name).join(', ') : (file?.name ?? '')
	);
</script>

<button
	type="button"
	class={cn(
		'relative flex w-full flex-col items-center justify-center rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer',
		dragover
			? 'border-chart-1 bg-chart-1/5'
			: hasFile
				? 'border-emerald-500/50 bg-emerald-500/5'
				: 'border-border hover:border-muted-foreground/50 hover:bg-accent/30'
	)}
	ondrop={handleDrop}
	ondragover={handleDragOver}
	ondragleave={handleDragLeave}
	onclick={() => inputEl?.click()}
	disabled={loading}
>
	{#if loading}
		<Loader2 class="h-8 w-8 text-muted-foreground animate-spin mb-2" />
		<span class="text-sm text-muted-foreground">Processing...</span>
	{:else if hasFile}
		<FileCheck class="h-8 w-8 text-emerald-400 mb-2" />
		<span class="text-sm text-foreground font-medium truncate max-w-full">{displayName}</span>
		<span class="text-xs text-muted-foreground mt-1">Click or drop to replace</span>
	{:else}
		<Upload class="h-8 w-8 text-muted-foreground mb-2" />
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
