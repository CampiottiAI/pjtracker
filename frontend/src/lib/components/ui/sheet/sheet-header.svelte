<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils.js';

	let { class: className, children, ...restProps }: HTMLAttributes<HTMLDivElement> = $props();
</script>

<div class={cn('flex flex-col space-y-2 p-6 text-left', className)} {...restProps}>
	{@render children?.()}
</div>
