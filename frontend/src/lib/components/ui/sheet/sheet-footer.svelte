<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils.js';

	let { class: className, children, ...restProps }: HTMLAttributes<HTMLDivElement> = $props();
</script>

<div
	class={cn('shrink-0 flex flex-col-reverse gap-2 border-t border-border bg-popover p-4 sm:flex-row sm:justify-end sm:px-6', className)}
	{...restProps}
>
	{@render children?.()}
</div>
