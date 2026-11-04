<script lang="ts">
	import PageHeader from '$lib/components/PageHeader.svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import {
		FileText,
		Receipt,
		Landmark,
		WalletCards
	} from 'lucide-svelte';

	type DocLink = {
		href: string;
		label: string;
		description: string;
		icon: typeof FileText;
	};

	const docs: DocLink[] = [
		{
			href: '/nfs',
			label: 'Notas Fiscais',
			description: 'NF-e de serviço (USD → BRL)',
			icon: FileText
		},
		{
			href: '/boletos',
			label: 'Boletos',
			description: 'Boletos com recibo de pagamento',
			icon: Receipt
		},
		{
			href: '/darfs',
			label: 'DARFs',
			description: 'DARFs com recibo',
			icon: Landmark
		},
		{
			href: '/irpj-csll',
			label: 'IRPJ/CSLL',
			description: 'Trimestral (mar/jun/set/dez)',
			icon: Landmark
		},
		{
			href: '/extratos',
			label: 'Extratos',
			description: 'Extrato, caixinha e Higlobe',
			icon: WalletCards
		}
	];
</script>

<div class="space-y-6">
	<PageHeader
		title="Documentos"
		description="Envie e acompanhe os documentos fiscais da sua empresa."
	/>

	<div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
		{#each docs as doc}
			<a href={doc.href} class="block group">
				<Card.Root class="h-full transition-colors group-hover:border-muted-foreground/30">
					<Card.Header>
						<div class="flex items-center gap-2">
							<doc.icon class="h-5 w-5 text-muted-foreground" />
							<Card.Title class="text-base">{doc.label}</Card.Title>
						</div>
						<Card.Description>{doc.description}</Card.Description>
					</Card.Header>
				</Card.Root>
			</a>
		{/each}
	</div>

</div>
