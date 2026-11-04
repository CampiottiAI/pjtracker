<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils.js';

	let { class: className, children, ...restProps }: HTMLAttributes<HTMLDivElement> = $props();
</script>

<div class={cn('shrink-0 flex flex-col space-y-1.5 border-b border-border px-6 py-5 pr-12 text-left', className)} {...restProps}>
	{@render children?.()}
</div>
