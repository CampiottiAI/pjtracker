<script lang="ts">
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { cn } from '$lib/utils.js';
	import { Check, AlertTriangle, X, Minus } from 'lucide-svelte';

	let {
		status,
		label
	}: {
		status: 'success' | 'warning' | 'error' | 'neutral';
		label: string;
	} = $props();

	const colorMap = {
		success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
		warning: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
		error: 'bg-red-500/15 text-red-400 border-red-500/25',
		neutral: 'bg-muted text-muted-foreground border-border'
	};

	const iconMap = {
		success: Check,
		warning: AlertTriangle,
		error: X,
		neutral: Minus
	};
</script>

<Badge variant="outline" class={cn('gap-1', colorMap[status])}>
	<svelte:component this={iconMap[status]} class="h-3 w-3" />
	{label}
</Badge>
