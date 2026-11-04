<script lang="ts">
	import type { SvelteHTMLElements } from 'svelte/elements';
	import { cn } from '$lib/utils.js';

	let { class: className, children, ...restProps }: SvelteHTMLElements['caption'] = $props();
</script>

<caption class={cn('text-muted-foreground mt-4 text-sm', className)} {...restProps}>
	{@render children?.()}
</caption>
