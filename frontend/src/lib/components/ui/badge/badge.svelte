<script lang="ts">
	import type { HTMLAttributes } from 'svelte/elements';
	import { cn } from '$lib/utils.js';
	import { badgeVariants, type Variant } from './index.js';

	let {
		class: className,
		variant = 'default',
		children,
		...restProps
	}: HTMLAttributes<HTMLDivElement> & { variant?: Variant } = $props();
</script>

<div class={cn(badgeVariants({ variant, className }))} {...restProps}>
	{@render children?.()}
</div>
