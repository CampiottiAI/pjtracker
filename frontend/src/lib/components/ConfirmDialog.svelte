<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';

	let {
		open = $bindable(false),
		title = 'Confirmar exclusão?',
		description = 'Esta ação não pode ser desfeita.',
		confirmLabel = 'Excluir',
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
			<Button variant="outline" onclick={() => (open = false)}>Cancelar</Button>
			<Button variant="destructive" onclick={handleConfirm} disabled={loading}>
				{loading ? 'Excluindo…' : confirmLabel}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
