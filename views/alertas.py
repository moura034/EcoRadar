"""Central de alertas estimados e histórico local."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from components.state import get_period
from components.ui import empty_state, hero, source_caption
from database.db import EcoRadarDatabase
from models.risk_index import RISK_COLORS
from services.dashboard_service import EcoRadarService


start, end = get_period()
service = EcoRadarService()
bundle = service.load_bundle(start, end)
hero(
    "Central de Alertas EcoRadar",
    "Sinais internos acionados por risco estimado. Um alerta não significa que um incêndio foi confirmado.",
    f"Alertas • {start:%d/%m/%Y} a {end:%d/%m/%Y}",
)

threshold = st.slider("Limite do índice para gerar alerta", min_value=30, max_value=90, value=55, step=5)
valid_risk = bundle.risk.dropna(subset=["risk_score"]).copy() if not bundle.risk.empty else pd.DataFrame()
candidates = valid_risk[valid_risk["risk_score"] >= threshold].copy() if not valid_risk.empty else valid_risk

if st.button("Gerar/atualizar alertas do recorte", type="primary", disabled=candidates.empty):
    candidates["observed_date"] = pd.to_datetime(candidates["observed_date"]).dt.date.astype(str)
    candidates["factors"] = candidates["factors_json"].map(
        lambda value: json.loads(value) if value else []
    )
    created = EcoRadarDatabase().create_alerts(candidates)
    st.success(f"Processamento concluído: {created} registro(s) inserido(s) ou atualizado(s).")
    st.rerun()

summary_cols = st.columns(4)
summary_cols[0].metric("Acima do limite", len(candidates))
summary_cols[1].metric("Críticos", int((candidates.get("risk_class") == "Crítico").sum()) if not candidates.empty else 0)
summary_cols[2].metric("Altos", int((candidates.get("risk_class") == "Alto").sum()) if not candidates.empty else 0)
summary_cols[3].metric("Histórico no período", len(bundle.alerts))

st.markdown("#### Situação atual")
if candidates.empty:
    empty_state("Nenhum município com dados válidos ultrapassa o limite configurado neste recorte.")
else:
    for row in candidates.sort_values("risk_score", ascending=False).head(30).itertuples():
        color = RISK_COLORS.get(row.risk_class, "#6b7280")
        factors = []
        if getattr(row, "factors_json", None):
            try:
                factors = json.loads(row.factors_json)
            except json.JSONDecodeError:
                factors = []
        with st.container(border=True):
            title_col, score_col = st.columns((4, 1))
            with title_col:
                st.markdown(
                    f'<span class="risk-pill" style="color:{color}">{row.risk_class}</span> '
                    f'<b style="font-size:1.05rem;margin-left:.5rem">{row.municipality}</b>',
                    unsafe_allow_html=True,
                )
                st.caption("Fatores: " + (", ".join(factors) if factors else "sem explicação persistida"))
                st.caption("Origem: INPE + Open-Meteo + IBGE • índice heurístico EcoRadar v1")
            with score_col:
                st.metric("Índice", f"{row.risk_score:.1f}/100")

st.markdown("#### Histórico de alertas")
history = EcoRadarDatabase().alerts(start.isoformat(), end.isoformat())
if history.empty:
    empty_state("O histórico ainda não contém alertas para o período.")
else:
    display = history.copy()
    display["factors_json"] = display["factors_json"].map(
        lambda value: ", ".join(json.loads(value)) if value else ""
    )
    display = display.rename(
        columns={
            "municipality": "Município",
            "risk_level": "Nível",
            "risk_score": "Índice",
            "observed_at": "Data de referência",
            "factors_json": "Fatores",
            "source_summary": "Origem",
            "status": "Status",
        }
    )
    st.dataframe(
        display[["Município", "Nível", "Índice", "Data de referência", "Fatores", "Origem", "Status"]],
        hide_index=True,
        width="stretch",
        column_config={"Índice": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f")},
    )

st.warning("Alertas desta página são estimativas preventivas; consulte autoridades e fontes oficiais para ocorrências confirmadas.")
source_caption("INPE Programa Queimadas", "Open-Meteo", "IBGE")
