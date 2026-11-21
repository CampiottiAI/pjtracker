<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { cn } from '$lib/utils.js';
	import { ApiError, downloadBackup, formatApiErrorMessage, getReady, triggerDownload } from '$lib/api/client.js';
	import { Button } from '$lib/components/ui/button';
	import { toast } from 'svelte-sonner';
	import {
		LayoutDashboard,
		Home,
		BarChart3,
		Menu,
		X,
		FolderOpen,
		FileText,
		Car,
		Download,
		LoaderCircle
	} from 'lucide-svelte';

	type NavItem = { href: string; label: string; icon: typeof LayoutDashboard };

	const primaryItems: NavItem[] = [
		{ href: '/', label: 'Fluxo', icon: LayoutDashboard },
		{ href: '/casa', label: 'Casa', icon: Home },
		{ href: '/carros', label: 'Carros', icon: Car },
		{ href: '/documentos', label: 'Documentos', icon: FolderOpen },
		{ href: '/analytics', label: 'Análises', icon: BarChart3 }
	];

	let mobileOpen = $state(false);
	let downloadingBackup = $state(false);
	let apiStatus = $state<'ok' | 'degraded' | 'down'>('down');

	async function handleBackupDownload() {
		if (downloadingBackup) return;
		downloadingBackup = true;
		try {
			const { blob, filename } = await downloadBackup();
			triggerDownload(blob, filename ?? 'pjtracker-backup.tar.gz');
		} catch (error) {
			toast.error(error instanceof ApiError ? formatApiErrorMessage(error.body) : 'Falha ao baixar backup');
		} finally {
			downloadingBackup = false;
		}
	}

	function isActive(href: string, pathname: string): boolean {
		if (href === '/') return pathname === '/';
		if (href === '/documentos') {
			return (
				pathname === '/documentos' ||
				pathname.startsWith('/nfs') ||
				pathname.startsWith('/boletos') ||
				pathname.startsWith('/darfs') ||
				pathname.startsWith('/irpj-csll') ||
				pathname.startsWith('/extratos')
			);
		}
		return pathname.startsWith(href);
	}

	async function checkStatus() {
		try {
			const r = await getReady();
			apiStatus = r.ready ? 'ok' : 'degraded';
		} catch {
			apiStatus = 'down';
		}
	}

	onMount(() => {
		checkStatus();
		const interval = setInterval(checkStatus, 30_000);
		return () => clearInterval(interval);
	});
</script>

<nav class="border-b border-border bg-card sticky top-0 z-40">
	<div class="mx-auto flex h-14 max-w-7xl items-center px-4 sm:px-6">
		<a href="/" class="mr-8 flex items-center gap-2 text-foreground font-semibold tracking-tight">
			<FileText class="h-5 w-5 text-primary" />
			<span>pjtracker</span>
		</a>

		<div class="hidden md:flex items-center gap-1">
			{#each primaryItems as item}
				{@const active = isActive(item.href, $page.url.pathname)}
				<a
					href={item.href}
					class={cn(
						'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
						active
							? 'bg-primary/10 text-primary'
							: 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
					)}
				>
					<item.icon class="h-4 w-4" />
					{item.label}
				</a>
			{/each}
		</div>

		<div class="flex-1"></div>

		<Button
			variant="ghost"
			size="sm"
			class="mr-2"
			disabled={downloadingBackup}
			onclick={handleBackupDownload}
			aria-label={downloadingBackup ? 'Preparando backup' : 'Baixar backup'}
			aria-busy={downloadingBackup}
			title="Baixar backup do banco de dados, PDFs e imagens"
		>
			{#if downloadingBackup}
				<LoaderCircle class="h-4 w-4 animate-spin" />
			{:else}
				<Download class="h-4 w-4" />
			{/if}
			<span class="hidden lg:inline">{downloadingBackup ? 'Preparando…' : 'Baixar backup'}</span>
		</Button>

		<div
			class="hidden md:flex items-center gap-2 text-xs text-muted-foreground"
			title="Status da conexão"
		>
			<span class={cn('h-1.5 w-1.5 rounded-full', apiStatus === 'ok' ? 'bg-success' : apiStatus === 'degraded' ? 'bg-warning' : 'bg-destructive-foreground')}></span>
			{apiStatus === 'ok' ? 'Conectado' : apiStatus === 'degraded' ? 'Conexão limitada' : 'Sem conexão'}
		</div>

		<button
			class="md:hidden ml-2 inline-flex items-center justify-center rounded-md p-2 text-muted-foreground hover:text-foreground hover:bg-accent"
			onclick={() => (mobileOpen = !mobileOpen)}
			aria-label="Abrir ou fechar menu"
			aria-expanded={mobileOpen}
		>
			{#if mobileOpen}
				<X class="h-5 w-5" />
			{:else}
				<Menu class="h-5 w-5" />
			{/if}
		</button>
	</div>

	{#if mobileOpen}
		<div class="md:hidden border-t border-border px-4 pb-3 pt-2 space-y-1">
			{#each primaryItems as item}
				{@const active = isActive(item.href, $page.url.pathname)}
				<a
					href={item.href}
					onclick={() => (mobileOpen = false)}
					class={cn(
						'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
						active
							? 'bg-primary/10 text-primary'
							: 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
					)}
				>
					<item.icon class="h-4 w-4" />
					{item.label}
				</a>
			{/each}
		</div>
	{/if}
</nav>
