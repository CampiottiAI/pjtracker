<script lang="ts">
	import BoletoLikePage from '$lib/components/BoletoLikePage.svelte';
	import {
		listDarfs,
		darfParsePreview,
		createDarf,
		deleteDarf,
		patchDarfFiscalMes,
		getDarfBarcodeDiff,
		updateDarfPdf,
		updateDarfReceipt,
		getDarf
	} from '$lib/api/client.js';
</script>

<BoletoLikePage
	domainLabel="DARF"
	routePrefix="darfs"
	listFn={listDarfs}
	parsePreviewFn={darfParsePreview}
	createFn={createDarf}
	deleteFn={deleteDarf}
	patchFiscalMesFn={patchDarfFiscalMes}
	getBarcodeDiffFn={getDarfBarcodeDiff}
	replacePdfFn={updateDarfPdf}
	replaceReceiptFn={updateDarfReceipt}
	getFn={getDarf}
/>
