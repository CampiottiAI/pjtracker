"""NF time-series points for analytics (from 3_Gráficos)."""

from __future__ import annotations

from datetime import date

from pjtracker.app import get_nf_entries, parse_nf_date_to_date


def nf_series_points(date_from: date, date_to: date) -> list[dict]:
    entries = get_nf_entries(date_from=date_from, date_to=date_to)
    chart_rows: list[dict] = []
    for row in entries:
        d = parse_nf_date_to_date(row.get("nf_date"))
        if d is None:
            continue
        rate = row.get("rate") or 0
        spread = row.get("spread") or 0
        effective_rate = rate * (1 - spread / 100)
        chart_rows.append(
            {
                "date": d.isoformat(),
                "usd": row.get("usd") or 0,
                "brl_no_spread": row.get("brl_no_spread") or 0,
                "brl_with_spread": row.get("brl_with_spread") or 0,
                "rate": rate,
                "spread": spread,
                "effective_rate": effective_rate,
            }
        )
    chart_rows.sort(key=lambda r: r["date"])
    return chart_rows
