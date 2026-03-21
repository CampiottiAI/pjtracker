<script lang="ts">
	import BoletoLikePage from '$lib/components/BoletoLikePage.svelte';
	import {
		listBoletos,
		boletoParsePreview,
		createBoleto,
		deleteBoleto,
		patchBoletoFiscalMes,
		getBoletoBarcodeDiff
	} from '$lib/api/client.js';
</script>

<BoletoLikePage
	domainLabel="Boleto"
	routePrefix="boletos"
	listFn={listBoletos}
	parsePreviewFn={boletoParsePreview}
	createFn={createBoleto}
	deleteFn={deleteBoleto}
	patchFiscalMesFn={patchBoletoFiscalMes}
	getBarcodeDiffFn={getBoletoBarcodeDiff}
/>
