<script lang="ts">
	import BoletoLikePage from '$lib/components/BoletoLikePage.svelte';
	import {
		listBoletos,
		boletoParsePreview,
		createBoleto,
		deleteBoleto,
		patchBoletoFiscalMes,
		getBoletoBarcodeDiff,
		updateBoletoPdf,
		updateBoletoReceipt,
		getBoleto
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
	replacePdfFn={updateBoletoPdf}
	replaceReceiptFn={updateBoletoReceipt}
	getFn={getBoleto}
/>
