"""Ranking pesquisável dos 224 municípios."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components.state import get_period
from components.ui import empty_state, hero, source_caption
from services.dashboard_service import EcoRadarService


start, end = get_period()
bundle = EcoRadarService().load_bundle(start, end)
hero(
    "Ranking de Risco Ambiental",
    "Ordene, pesquise e filtre os municípios do Piauí combinando observações de focos, meteorologia e índice estimado.",
    f"224 municípios • {start:%d/%m/%Y} a {end:%d/%m/%Y}",
)

if bundle.ranking.empty:
    empty_state("O ranking depende do cadastro municipal do IBGE. Sincronize as fontes para continuar.")
    st.stop()

search_col, class_col, sort_col = st.columns((1.4, 1, 1))
with search_col:
    search = st.text_input("Pesquisar município", placeholder="Ex.: Teresina")
with class_col:
    classes = st.multiselect(
        "Classificação",
        ["Baixo", "Moderado", "Alto", "Crítico", "Indisponível"],
        default=["Baixo", "Moderado", "Alto", "Crítico", "Indisponível"],
    )
with sort_col:
    sort_label = st.selectbox(
        "Ordenar por",
        ["Índice de risco", "Focos observados", "Temperatura", "Precipitação"],
    )

ranking = bundle.ranking.copy()
if search:
    ranking = ranking[ranking["municipality"].str.contains(search, case=False, na=False)]
ranking = ranking[ranking["risk_class"].isin(classes)]
sort_map = {
    "Índice de risco": "risk_score",
    "Focos observados": "fire_count",
    "Temperatura": "temperature_c",
    "Precipitação": "precipitation_mm",
}
ranking = ranking.sort_values(sort_map[sort_label], ascending=False, na_position="last").reset_index(drop=True)
ranking["position"] = range(1, len(ranking) + 1)

display = ranking.rename(
    columns={
        "position": "Posição",
        "municipality": "Município",
        "fire_count": "Focos",
        "temperature_c": "Temperatura (°C)",
        "humidity_pct": "Umidade (%)",
        "wind_speed_kmh": "Vento (km/h)",
        "precipitation_mm": "Precipitação (mm)",
        "risk_score": "Índice de risco",
        "risk_class": "Classificação",
    }
)
columns = [
    "Posição", "Município", "Focos", "Temperatura (°C)", "Umidade (%)", "Vento (km/h)",
    "Precipitação (mm)", "Índice de risco", "Classificação",
]
st.dataframe(
    display[columns],
    width="stretch",
    hide_index=True,
    height=650,
    column_config={
        "Posição": st.column_config.NumberColumn(width="small", format="%d"),
        "Focos": st.column_config.NumberColumn(format="%d"),
        "Temperatura (°C)": st.column_config.NumberColumn(format="%.1f"),
        "Umidade (%)": st.column_config.NumberColumn(format="%.1f"),
        "Vento (km/h)": st.column_config.NumberColumn(format="%.1f"),
        "Precipitação (mm)": st.column_config.NumberColumn(format="%.1f"),
        "Índice de risco": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f"),
    },
)
st.caption(f"{len(ranking)} município(s) exibido(s). Valores ausentes permanecem em branco.")
source_caption("Focos: INPE", "Meteorologia: Open-Meteo", "Municípios: IBGE")
