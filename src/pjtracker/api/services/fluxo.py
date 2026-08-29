"""Fluxo (home) aggregation: casa + saques + company remainder."""

from __future__ import annotations

from pjtracker.api.services.casa import get_casa_summary_for_month
from pjtracker.api.services.fiscal_months import month_completeness
from pjtracker.api.services.withdraws import compute_withdraw_summary, previous_fiscal_mes
from pjtracker.app import get_darfs, get_extratos, get_irpj_cslls, get_nf_entries, get_withdraws


def _month_taxes_brl(fiscal_mes: str) -> float:
    total = 0.0
    for row in get_darfs(fiscal_mes=fiscal_mes):
        if row.get("value") is not None:
            total += float(row["value"])
    for row in get_irpj_cslls(fiscal_mes=fiscal_mes):
        if row.get("value") is not None:
            total += float(row["value"])
    return round(total, 2)


def _month_nf_income_brl(fiscal_mes: str) -> float:
    total = sum(
        float(row.get("brl_with_spread") or 0) for row in get_nf_entries(fiscal_mes=fiscal_mes)
    )
    return round(total, 2)


def _extrato_saldo_final(fiscal_mes: str) -> tuple[float | None, bool]:
    extratos = get_extratos(fiscal_mes=fiscal_mes)
    if not extratos:
        return None, False
    saldo = extratos[0].get("saldo_final")
    if saldo is None:
        return None, True
    return round(float(saldo), 2), True


def _completeness_missing_count(completeness: dict) -> int:
    missing = 0
    if not completeness.get("nfs_ok"):
        missing += max(0, 2 - completeness.get("nfs_count", 0))
    if not completeness.get("boletos_ok"):
        missing += 1
    if not completeness.get("darfs_ok"):
        missing += 1
    if completeness.get("irpj_csll_required") and not completeness.get("irpj_csll_ok"):
        missing += 1
    if not completeness.get("extratos_ok"):
        missing += 1
    return missing


def build_fluxo(fiscal_mes: str) -> dict:
    withdraw_items = get_withdraws(fiscal_mes=fiscal_mes)
    withdraw_summary = compute_withdraw_summary(withdraw_items, fiscal_mes=fiscal_mes)
    casa = get_casa_summary_for_month(fiscal_mes)
    completeness = month_completeness(fiscal_mes)

    saques_total = withdraw_summary["total_brl"]
    primary_share = casa["primary_share_brl"]
    surplus = round(saques_total - primary_share, 2)
    covers = surplus >= 0

    saldo_final, has_extrato = _extrato_saldo_final(fiscal_mes)
    taxes_brl = _month_taxes_brl(fiscal_mes)
    nf_income_brl = _month_nf_income_brl(fiscal_mes)

    if saldo_final is not None:
        restante_brl = saldo_final
        restante_estimated = False
    else:
        restante_brl = round(nf_income_brl - taxes_brl - saques_total, 2)
        restante_estimated = True

    prev_mes = previous_fiscal_mes(fiscal_mes)

    return {
        "fiscal_mes": fiscal_mes,
        "previous_fiscal_mes": prev_mes,
        "withdraw_summary": withdraw_summary,
        "casa": casa,
        "coverage": {
            "covers_household": covers,
            "surplus_brl": max(0.0, surplus),
            "shortfall_brl": max(0.0, -surplus),
            "saques_brl": saques_total,
            "primary_share_brl": primary_share,
            "household_total_brl": casa["household_total_brl"],
        },
        "company": {
            "saldo_final_brl": saldo_final,
            "has_extrato": has_extrato,
            "restante_brl": restante_brl,
            "restante_estimated": restante_estimated,
            "taxes_brl": taxes_brl,
            "nf_income_brl": nf_income_brl,
        },
        "completeness": completeness,
        "completeness_missing_count": _completeness_missing_count(completeness),
    }


def fluxo_series_months(months: list[str]) -> list[dict]:
    """Per-month points for analytics: saques vs primary casa share."""
    points: list[dict] = []
    for fm in sorted(months):
        withdraw_items = get_withdraws(fiscal_mes=fm)
        withdraw_summary = compute_withdraw_summary(withdraw_items, fiscal_mes=fm)
        casa = get_casa_summary_for_month(fm)
        points.append(
            {
                "fiscal_mes": fm,
                "saques_brl": withdraw_summary["total_brl"],
                "primary_share_brl": casa["primary_share_brl"],
                "household_total_brl": casa["household_total_brl"],
                "previous_month_income_brl": withdraw_summary["previous_month_income_brl"],
                "casa_saved": casa["saved"],
            }
        )
    return points
