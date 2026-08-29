"""Bill split logic for household expenses (N people, optional cc_reserved slice)."""

__all__ = ["compute_split_n", "compute_split"]


def compute_split_n(
    amounts: list[float],
    nubank: float,
    pcts: list[float],
    *,
    cc_reserved_amount: float = 0.0,
    cc_reserved_person_index: int | None = None,
) -> dict:
    """
    Compute split of total monthly expenses for N people.

    amounts[i] = total already paid by person i
    pcts[i] = share of total that person i should pay (must sum to 1.0)
    total (reported) = sum(amounts) + nubank

    Without cc_reserved: nubank_per_person[i] = pcts[i] * total - amounts[i].

    With cc_reserved_amount R assigned to index k:
    T = sum(amounts) + (nubank - R), and
    i != k: nubank_per_person[i] = pcts[i] * T - amounts[i]
    k: nubank_per_person[k] = R + pcts[k] * T - amounts[k]

    reimbursement[i] = max(0, -nubank_per_person[i])
    """
    n = len(amounts)
    if n != len(pcts):
        raise ValueError("amounts and pcts must have same length")
    if abs(sum(pcts) - 1.0) > 1e-9:
        raise ValueError("pcts must sum to 1.0")

    total = sum(amounts) + nubank
    R_raw = float(cc_reserved_amount)
    if R_raw < -1e-9:
        raise ValueError("cc_reserved_amount cannot be negative")
    if R_raw > nubank + 1e-9:
        raise ValueError("cc_reserved_amount cannot exceed credit card bill")
    R = max(0.0, R_raw)

    effective_R = R if R > 1e-9 else 0.0
    k = cc_reserved_person_index
    if effective_R > 1e-9:
        if k is None or k < 0 or k >= n:
            raise ValueError(
                "cc_reserved_person_index required and valid when cc_reserved_amount > 0"
            )

    if effective_R <= 1e-9:
        nubank_per_person = [pcts[i] * total - amounts[i] for i in range(n)]
        ix_out: int | None = None
    else:
        S = sum(amounts)
        T = S + (nubank - effective_R)
        nubank_per_person = []
        for i in range(n):
            if i == k:
                nubank_per_person.append(effective_R + pcts[i] * T - amounts[i])
            else:
                nubank_per_person.append(pcts[i] * T - amounts[i])
        ix_out = k

    reimbursements = [-x if x < 0 else 0.0 for x in nubank_per_person]
    return {
        "total": total,
        "nubank_per_person": nubank_per_person,
        "reimbursements": reimbursements,
        "pcts": list(pcts),
        "cc_reserved_amount": R,
        "cc_reserved_person_index": ix_out,
    }


def compute_split(
    rael: float,
    fer: float,
    nubank: float,
    rael_pct: float = 0.6,
    *,
    cc_reserved_amount: float = 0.0,
    cc_reserved_person_index: int | None = None,
) -> dict:
    """Two-person wrapper (Rael & Fer)."""
    result = compute_split_n(
        [rael, fer],
        nubank,
        [rael_pct, 1.0 - rael_pct],
        cc_reserved_amount=cc_reserved_amount,
        cc_reserved_person_index=cc_reserved_person_index,
    )
    return {
        "total": result["total"],
        "rael_nubank": result["nubank_per_person"][0],
        "fer_nubank": result["nubank_per_person"][1],
        "rael_reimbursement": result["reimbursements"][0],
        "fer_reimbursement": result["reimbursements"][1],
        "rael_pct": result["pcts"][0],
        "fer_pct": result["pcts"][1],
        "cc_reserved_amount": result["cc_reserved_amount"],
        "cc_reserved_person_index": result["cc_reserved_person_index"],
    }
