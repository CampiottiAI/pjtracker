<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';

	let {
		open = $bindable(false),
		title = 'Are you sure?',
		description = 'This action cannot be undone.',
		confirmLabel = 'Delete',
		onconfirm
	}: {
		open?: boolean;
		title?: string;
		description?: string;
		confirmLabel?: string;
		onconfirm: () => void | Promise<void>;
	} = $props();

	let loading = $state(false);

	async function handleConfirm() {
		loading = true;
		try {
			await onconfirm();
			open = false;
		} finally {
			loading = false;
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Content>
		<Dialog.Header>
			<Dialog.Title>{title}</Dialog.Title>
			<Dialog.Description>{description}</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer>
			<Button variant="outline" onclick={() => (open = false)}>Cancel</Button>
			<Button variant="destructive" onclick={handleConfirm} disabled={loading}>
				{loading ? 'Deleting...' : confirmLabel}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
