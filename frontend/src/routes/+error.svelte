<script lang="ts">
	import { page } from '$app/stores';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { AlertTriangle } from 'lucide-svelte';
</script>

<div class="flex items-center justify-center py-24">
	<Card.Root class="max-w-md w-full">
		<Card.Content class="pt-6 text-center space-y-4">
			<AlertTriangle class="mx-auto h-12 w-12 text-amber-400" />
			<h2 class="text-xl font-semibold">{$page.status}</h2>
			<p class="text-muted-foreground text-sm">{$page.error?.message ?? 'Something went wrong.'}</p>
			<Button variant="outline" onclick={() => window.location.href = '/'}>
				Back to Dashboard
			</Button>
		</Card.Content>
	</Card.Root>
</div>
