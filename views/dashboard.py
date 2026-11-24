"""Visão geral da situação ambiental."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.charts import PLOTLY_CONFIG, style_figure
from components.state import get_period
from components.ui import empty_state, format_number, hero, section_label, source_caption
from models.risk_index import RISK_COLORS
from services.dashboard_service import EcoRadarService


start, end = get_period()
bundle = EcoRadarService().load_bundle(start, end)

hero(
    "Panorama ambiental do Piauí",
    "Focos de calor observados, condições meteorológicas e risco heurístico municipal em uma única leitura operacional.",
    f"Visão geral • {start:%d/%m/%Y} a {end:%d/%m/%Y}",
)

if not bundle.has_observations:
    empty_state(
        "Ainda não há observações locais para este período.<br>Use <b>Sincronizar fontes oficiais</b> no menu lateral. "
        "O EcoRadar não preenche lacunas com valores fictícios."
    )
    st.stop()

fires = bundle.fire_spots.copy()
weather = bundle.weather.copy()
risk = bundle.risk.copy()
if not fires.empty:
    fires["observed_at"] = pd.to_datetime(fires["observed_at"], errors="coerce")
if not weather.empty:
    weather["observed_date"] = pd.to_datetime(weather["observed_date"], errors="coerce")

valid_risk = risk[pd.to_numeric(risk.get("risk_score"), errors="coerce").notna()] if not risk.empty else risk
high_count = int(valid_risk["risk_class"].isin(["Alto", "Crítico"]).sum()) if not valid_risk.empty else None
highest = valid_risk.sort_values("risk_score", ascending=False).head(1) if not valid_risk.empty else pd.DataFrame()

section_label("Indicadores do período")
first_row = st.columns(3)
first_row[0].metric("Focos observados", format_number(len(fires)), help="Detecções presentes nos CSVs oficiais do INPE.")
first_row[1].metric(
    "Municípios com focos",
    format_number(fires["municipality_id"].nunique() if not fires.empty else 0),
)
first_row[2].metric("Risco alto ou crítico", format_number(high_count))
second_row = st.columns(3)
second_row[0].metric(
    "Temperatura média",
    format_number(weather["temperature_c"].mean() if not weather.empty else None, 1, " °C"),
)
second_row[1].metric(
    "Umidade média",
    format_number(weather["humidity_pct"].mean() if not weather.empty else None, 1, "%"),
)
second_row[2].metric(
    "Maior risco estimado",
    highest.iloc[0]["municipality"] if not highest.empty else "—",
    format_number(highest.iloc[0]["risk_score"] if not highest.empty else None, 1, "/100"),
    help="Índice heurístico; não representa incêndio confirmado nem previsão validada por IA.",
)

section_label("Comportamento e distribuição")
left, right = st.columns((1.55, 1), gap="large")
with left:
    if not fires.empty:
        daily = fires.groupby(fires["observed_at"].dt.date).size().rename("focos").reset_index()
        daily.columns = ["data", "focos"]
        figure = px.area(
            daily,
            x="data",
            y="focos",
            title="Evolução diária dos focos observados",
            markers=True,
            color_discrete_sequence=["#49e596"],
        )
        figure.update_traces(line=dict(width=2.5), fillcolor="rgba(73,229,150,.16)")
        figure.update_layout(xaxis_title=None, yaxis_title="Focos")
        st.plotly_chart(style_figure(figure), width="stretch", config=PLOTLY_CONFIG)
    else:
        empty_state("O INPE não retornou focos válidos no período selecionado.")

with right:
    if not valid_risk.empty:
        distribution = (
            valid_risk["risk_class"].value_counts().reindex(["Baixo", "Moderado", "Alto", "Crítico"]).fillna(0)
        )
        figure = px.pie(
            values=distribution.values,
            names=distribution.index,
            hole=.66,
            title="Municípios por faixa de risco",
            color=distribution.index,
            color_discrete_map=RISK_COLORS,
        )
        figure.update_traces(textinfo="percent+label", hovertemplate="%{label}: %{value}<extra></extra>")
        st.plotly_chart(style_figure(figure), width="stretch", config=PLOTLY_CONFIG)
    else:
        empty_state("Risco indisponível: faltam variáveis meteorológicas válidas.")

bottom_left, bottom_right = st.columns(2, gap="large")
with bottom_left:
    if not fires.empty:
        top_fires = fires.groupby("municipality").size().nlargest(10).sort_values().rename("focos").reset_index()
        figure = px.bar(
            top_fires,
            x="focos",
            y="municipality",
            orientation="h",
            title="Municípios com mais focos",
            color="focos",
            color_continuous_scale=["#234c36", "#ff8b3d"],
        )
        figure.update_layout(xaxis_title="Focos", yaxis_title=None, coloraxis_showscale=False)
        st.plotly_chart(style_figure(figure, 390), width="stretch", config=PLOTLY_CONFIG)

with bottom_right:
    if not valid_risk.empty:
        top_risk = valid_risk.nlargest(10, "risk_score").sort_values("risk_score")
        figure = px.bar(
            top_risk,
            x="risk_score",
            y="municipality",
            orientation="h",
            title="Maiores índices heurísticos",
            color="risk_class",
            color_discrete_map=RISK_COLORS,
            hover_data={"risk_score": ":.1f"},
        )
        figure.update_layout(xaxis_title="Índice (0–100)", yaxis_title=None, legend_title=None)
        st.plotly_chart(style_figure(figure, 390), width="stretch", config=PLOTLY_CONFIG)

if not bundle.source_updates.empty:
    last_update = pd.to_datetime(bundle.source_updates["updated_at"], errors="coerce").max()
    st.caption(f"Última atualização local registrada: {last_update:%d/%m/%Y %H:%M}.")
source_caption("INPE Programa Queimadas", "IBGE", "Open-Meteo")
st.markdown(
    '<div class="eco-note"><b>Leitura correta:</b> focos são observações por satélite. O índice municipal é uma estimativa '
    'heurística baseada em clima, histórico e sazonalidade; ele não confirma a existência de incêndio.</div>',
    unsafe_allow_html=True,
)
