"""Gráficos – NF values in USD, BRL, and rates with/without spread."""

from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from src.app import get_nf_entries, init_db, parse_nf_date_to_date

init_db()

st.title("Gráficos")

if "graf_applied_date_from" not in st.session_state:
    st.session_state.graf_applied_date_from = date.today() - timedelta(days=30)
if "graf_applied_date_to" not in st.session_state:
    st.session_state.graf_applied_date_to = date.today()

date_from = st.date_input(
    "De", value=st.session_state.graf_applied_date_from, format="DD/MM/YYYY"
)
date_to = st.date_input(
    "Até", value=st.session_state.graf_applied_date_to, format="DD/MM/YYYY"
)

if date_from > date_to:
    st.warning("A data 'De' deve ser anterior ou igual à data 'Até'.")

if st.button("Aplicar filtro"):
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    st.session_state.graf_applied_date_from = date_from
    st.session_state.graf_applied_date_to = date_to
    st.rerun()

date_from = st.session_state.graf_applied_date_from
date_to = st.session_state.graf_applied_date_to
entries = get_nf_entries(date_from=date_from, date_to=date_to)

# Build chart data: parse date, compute effective rate, sort by date ascending
# Rows without valid nf_date are skipped so x-axis is consistent
chart_rows = []
for row in entries:
    d = parse_nf_date_to_date(row.get("nf_date"))
    if d is None:
        continue
    rate = row.get("rate") or 0
    spread = row.get("spread") or 0
    effective_rate = rate * (1 - spread / 100)
    chart_rows.append(
        {
            "date": d,
            "usd": row.get("usd") or 0,
            "brl_no_spread": row.get("brl_no_spread") or 0,
            "brl_with_spread": row.get("brl_with_spread") or 0,
            "rate": rate,
            "effective_rate": effective_rate,
        }
    )
chart_rows.sort(key=lambda r: r["date"])

if not chart_rows:
    st.info("Nenhuma NF no período.")
    st.stop()

dates = [r["date"] for r in chart_rows]

# Graph 1 – Values in USD
fig_usd = go.Figure()
fig_usd.add_trace(
    go.Scatter(
        x=dates, y=[r["usd"] for r in chart_rows], mode="lines+markers", name="USD"
    )
)
fig_usd.update_layout(
    title="Valor das NFs em USD",
    xaxis_title="Data",
    yaxis_title="USD",
)
st.plotly_chart(fig_usd, use_container_width=True)

# Graph 2 – Values in Reais (both series)
fig_brl = go.Figure()
fig_brl.add_trace(
    go.Scatter(
        x=dates,
        y=[r["brl_no_spread"] for r in chart_rows],
        mode="lines+markers",
        name="Sem spread",
    )
)
fig_brl.add_trace(
    go.Scatter(
        x=dates,
        y=[r["brl_with_spread"] for r in chart_rows],
        mode="lines+markers",
        name="Com spread",
    )
)
fig_brl.update_layout(
    title="Valor das NFs em Reais",
    xaxis_title="Data",
    yaxis_title="BRL",
)
st.plotly_chart(fig_brl, use_container_width=True)

# Graph 3 – Rates with and without spread
fig_rates = go.Figure()
fig_rates.add_trace(
    go.Scatter(
        x=dates,
        y=[r["rate"] for r in chart_rows],
        mode="lines+markers",
        name="Sem spread",
    )
)
fig_rates.add_trace(
    go.Scatter(
        x=dates,
        y=[r["effective_rate"] for r in chart_rows],
        mode="lines+markers",
        name="Com spread",
    )
)
fig_rates.update_layout(
    title="Cotação com e sem spread",
    xaxis_title="Data",
    yaxis_title="BRL/USD",
)
st.plotly_chart(fig_rates, use_container_width=True)
