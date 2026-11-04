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
		success: 'bg-muted/50 text-muted-foreground border-border',
		warning: 'bg-warning/10 text-warning border-warning/25',
		error: 'bg-destructive-foreground/10 text-destructive-foreground border-destructive-foreground/25',
		neutral: 'bg-muted text-muted-foreground border-border'
	};

	const iconMap = {
		success: Check,
		warning: AlertTriangle,
		error: X,
		neutral: Minus
	};
	const Icon = $derived(iconMap[status]);
</script>

<Badge variant="outline" class={cn('gap-1', colorMap[status])}>
	<Icon class="h-3 w-3" />
	{label}
</Badge>
