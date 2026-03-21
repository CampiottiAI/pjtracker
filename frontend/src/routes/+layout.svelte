<script lang="ts">
	import '../app.css';
	import Navbar from '$lib/components/Navbar.svelte';
	import { Toaster } from '$lib/components/ui/sonner/index.js';
	import favicon from '$lib/assets/favicon.svg';

	let { children } = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>pjtracker</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<Navbar />
	<main class="mx-auto max-w-7xl px-4 py-6 sm:px-6">
		{@render children()}
	</main>
</div>

<Toaster position="bottom-right" />
