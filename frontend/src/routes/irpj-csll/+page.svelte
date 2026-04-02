<script lang="ts">
	import BoletoLikePage from '$lib/components/BoletoLikePage.svelte';
	import {
		listIrpjCsll,
		irpjCsllParsePreview,
		createIrpjCsll,
		deleteIrpjCsll,
		patchIrpjCsllFiscalMes,
		patchIrpjCsllFields,
		getIrpjCsllBarcodeDiff,
		updateIrpjCsllPdf,
		updateIrpjCsllReceipt,
		getIrpjCsll
	} from '$lib/api/client.js';
</script>

<BoletoLikePage
	domainLabel="IRPJ/CSLL"
	routePrefix="irpj-csll"
	listFn={listIrpjCsll}
	parsePreviewFn={irpjCsllParsePreview}
	createFn={createIrpjCsll}
	deleteFn={deleteIrpjCsll}
	patchFiscalMesFn={patchIrpjCsllFiscalMes}
	patchFieldsFn={patchIrpjCsllFields}
	getBarcodeDiffFn={getIrpjCsllBarcodeDiff}
	replacePdfFn={updateIrpjCsllPdf}
	replaceReceiptFn={updateIrpjCsllReceipt}
	getFn={getIrpjCsll}
/>
