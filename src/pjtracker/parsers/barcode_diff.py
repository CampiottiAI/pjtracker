"""Barcode diff formatting for document vs receipt comparison."""

import difflib


def format_barcode_diff(
    doc_digits: str | None,
    receipt_digits: str | None,
    doc_label: str = "Documento",
    receipt_label: str = "Comprovante",
) -> str:
    """Return a unified-diff-style string between the two barcode digit strings.

    If both are equal or either is empty, returns a short message so callers
    can skip rendering the diff.
    """
    if not doc_digits or not receipt_digits:
        return "Um dos códigos não está disponível."
    if doc_digits == receipt_digits:
        return "Nenhuma diferença."
    lines = list(
        difflib.unified_diff(
            [doc_digits],
            [receipt_digits],
            fromfile=doc_label,
            tofile=receipt_label,
            lineterm="",
        )
    )
    return "\n".join(lines) if lines else "Nenhuma diferença."
