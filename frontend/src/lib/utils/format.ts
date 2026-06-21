const MONTH_NAMES: Record<string, string> = {
	'01': 'Janeiro',
	'02': 'Fevereiro',
	'03': 'Março',
	'04': 'Abril',
	'05': 'Maio',
	'06': 'Junho',
	'07': 'Julho',
	'08': 'Agosto',
	'09': 'Setembro',
	'10': 'Outubro',
	'11': 'Novembro',
	'12': 'Dezembro'
};

/** "2025-03" -> "Março 2025" */
export function formatFiscalMes(value: string | null | undefined): string {
	if (!value) return '\u2014';
	const [year, month] = value.split('-');
	const name = MONTH_NAMES[month];
	if (!name || !year) return value;
	return `${name} ${year}`;
}

/** Format a number as BRL currency. */
export function formatBrl(value: number | null | undefined): string {
	if (value == null) return '\u2014';
	return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/** Format a number as USD currency. */
export function formatUsd(value: number | null | undefined): string {
	if (value == null) return '\u2014';
	return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

/** Format a number with fixed decimals. */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
	if (value == null) return '\u2014';
	return value.toFixed(decimals);
}

/** Format a rate as percentage string. */
export function formatPercent(value: number | null | undefined): string {
	if (value == null) return '\u2014';
	return `${value.toFixed(2)}%`;
}

/** Format a withdraw date (ISO YYYY-MM-DD or DD/MM/YYYY). */
export function formatWithdrawDate(value: string | null | undefined): string {
	if (!value) return '\u2014';
	const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
	if (isoMatch) {
		const [, year, month, day] = isoMatch;
		return `${day}/${month}/${year}`;
	}
	return formatDateBr(value);
}

/**
 * Parse a date string that may be DD/MM/YYYY or DD/MM/YYYY HH:MM:SS
 * into a short display format.
 */
export function formatDateBr(value: string | null | undefined): string {
	if (!value) return '\u2014';
	const parts = value.split(' ')[0];
	return parts ?? value;
}
