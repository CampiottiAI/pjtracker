<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils.js';

	let { class: className, children, ...restProps }: HTMLAttributes<HTMLTableRowElement> = $props();
</script>

<tr
	class={cn(
		'hover:bg-muted/50 data-[state=selected]:bg-muted border-b transition-colors',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</tr>
