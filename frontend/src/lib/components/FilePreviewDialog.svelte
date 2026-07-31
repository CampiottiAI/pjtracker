<script lang="ts">
	import { onDestroy, untrack } from 'svelte';
	import {
		ApiError,
		formatApiErrorMessage,
		downloadBlob,
		triggerDownload
	} from '$lib/api/client.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Download, Loader2 } from 'lucide-svelte';

	let {
		open = $bindable(false),
		path = $bindable<string | null>(null),
		title = 'Preview',
		fallbackFilename = 'file'
	}: {
		open?: boolean;
		path?: string | null;
		title?: string;
		fallbackFilename?: string;
	} = $props();

	let loading = $state(false);
	let error = $state<string | null>(null);
	let objectUrl = $state<string | null>(null);
	let blob = $state<Blob | null>(null);
	let filename = $state<string | undefined>();
	let mime = $state('');
	let loadSeq = 0;

	const isImage = $derived(mime.startsWith('image/'));
	const isPdf = $derived(
		mime === 'application/pdf' ||
			mime === 'application/x-pdf' ||
			(filename ?? fallbackFilename).toLowerCase().endsWith('.pdf')
	);

	function revoke() {
		if (objectUrl) {
			URL.revokeObjectURL(objectUrl);
			objectUrl = null;
		}
		blob = null;
		mime = '';
		filename = undefined;
		error = null;
	}

	function guessMime(name: string, current: string): string {
		if (current && current !== 'application/octet-stream') return current;
		const lower = name.toLowerCase();
		if (lower.endsWith('.pdf')) return 'application/pdf';
		if (lower.endsWith('.png')) return 'image/png';
		if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
		if (lower.endsWith('.gif')) return 'image/gif';
		if (lower.endsWith('.webp')) return 'image/webp';
		return current || '';
	}

	async function load(p: string) {
		const seq = ++loadSeq;
		loading = true;
		error = null;
		if (objectUrl) {
			URL.revokeObjectURL(objectUrl);
			objectUrl = null;
		}
		blob = null;
		try {
			const result = await downloadBlob(p);
			if (seq !== loadSeq) return;
			filename = result.filename;
			const name = filename ?? fallbackFilename;
			mime = guessMime(name, result.blob.type || '');
			blob =
				mime && mime !== result.blob.type ? new Blob([result.blob], { type: mime }) : result.blob;
			objectUrl = URL.createObjectURL(blob);
		} catch (e) {
			if (seq !== loadSeq) return;
			error = e instanceof ApiError ? formatApiErrorMessage(e.body) : 'Failed to load file';
		} finally {
			if (seq === loadSeq) loading = false;
		}
	}

	// Only `open`/`path` may be tracked here; load()/revoke() touch internal state
	// that would otherwise re-trigger this effect and restart the fetch forever.
	$effect(() => {
		const nextOpen = open;
		const nextPath = path;
		untrack(() => {
			if (nextOpen && nextPath) {
				void load(nextPath);
			} else if (!nextOpen) {
				loadSeq += 1;
				revoke();
			}
		});
	});

	onDestroy(() => {
		loadSeq += 1;
		revoke();
	});

	function handleDownload() {
		if (blob) triggerDownload(blob, filename ?? fallbackFilename);
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content
		class="flex max-h-[90vh] w-[min(96vw,56rem)] max-w-none flex-col gap-3 overflow-hidden p-4 sm:rounded-lg"
	>
		<Dialog.Header class="pr-8">
			<Dialog.Title>{title}</Dialog.Title>
			<Dialog.Description class="sr-only">In-browser document preview</Dialog.Description>
		</Dialog.Header>

		<div class="min-h-0 flex-1 overflow-auto rounded-md border border-border bg-muted/30">
			{#if loading}
				<div class="flex h-[60vh] items-center justify-center">
					<Loader2 class="h-6 w-6 animate-spin text-muted-foreground" />
				</div>
			{:else if error}
				<div
					class="flex h-[40vh] items-center justify-center px-4 text-center text-sm text-destructive-foreground"
				>
					{error}
				</div>
			{:else if objectUrl && isImage}
				<div class="flex max-h-[75vh] items-center justify-center p-2">
					<img src={objectUrl} alt={title} class="max-h-[75vh] max-w-full object-contain" />
				</div>
			{:else if objectUrl && isPdf}
				<iframe title={title} src={objectUrl} class="h-[75vh] w-full border-0"></iframe>
			{:else if objectUrl}
				<div
					class="flex h-[40vh] flex-col items-center justify-center gap-3 px-4 text-sm text-muted-foreground"
				>
					<p>Preview is not available for this file type.</p>
					<Button variant="outline" size="sm" onclick={handleDownload}>
						<Download class="h-3.5 w-3.5" />
						Download
					</Button>
				</div>
			{/if}
		</div>

		<Dialog.Footer>
			<Button variant="outline" onclick={() => (open = false)}>Close</Button>
			<Button onclick={handleDownload} disabled={!blob || loading}>
				<Download class="h-3.5 w-3.5" />
				Download
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
