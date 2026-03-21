<script lang="ts">
	import { Dialog as SheetPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils.js';
	import { X } from 'lucide-svelte';
	import SheetOverlay from './sheet-overlay.svelte';

	let {
		class: className,
		side = 'right',
		children,
		...restProps
	}: SheetPrimitive.ContentProps & { side?: 'top' | 'bottom' | 'left' | 'right' } = $props();

	const sideClasses = {
		top: 'inset-x-0 top-0 border-b data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top',
		bottom:
			'inset-x-0 bottom-0 border-t data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
		left: 'inset-y-0 left-0 h-full w-3/4 border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left sm:max-w-sm',
		right:
			'inset-y-0 right-0 h-full w-3/4 border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right sm:max-w-lg'
	} as const;
</script>

<SheetPrimitive.Portal>
	<SheetOverlay />
	<SheetPrimitive.Content
		class={cn(
			'bg-background data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:duration-300 data-[state=open]:duration-500 fixed z-50 gap-4 shadow-lg transition ease-in-out',
			sideClasses[side],
			className
		)}
		{...restProps}
	>
		{@render children?.()}
		<SheetPrimitive.Close
			class="ring-offset-background focus:ring-ring data-[state=open]:bg-secondary absolute top-4 right-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:pointer-events-none"
		>
			<X class="h-4 w-4" />
			<span class="sr-only">Close</span>
		</SheetPrimitive.Close>
	</SheetPrimitive.Content>
</SheetPrimitive.Portal>
