"""Análises temporais baseadas somente nos dados persistidos."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.charts import PLOTLY_CONFIG, style_figure
from components.state import get_period
from components.ui import empty_state, hero, source_caption
from services.dashboard_service import EcoRadarService


start, end = get_period()
bundle = EcoRadarService().load_bundle(start, end)
hero(
    "Análise temporal",
    "Explore sazonalidade, evolução diária e relações entre focos observados e condições meteorológicas.",
    f"Histórico local • {start:%d/%m/%Y} a {end:%d/%m/%Y}",
)

fires = bundle.fire_spots.copy()
weather = bundle.weather.copy()
if fires.empty and weather.empty:
    empty_state("Não existem observações persistidas para o intervalo selecionado.")
    st.stop()

if not fires.empty:
    fires["observed_at"] = pd.to_datetime(fires["observed_at"], errors="coerce")
    fires["date"] = fires["observed_at"].dt.normalize()
    fires["month"] = fires["observed_at"].dt.to_period("M").astype(str)
if not weather.empty:
    weather["observed_date"] = pd.to_datetime(weather["observed_date"], errors="coerce")

left, right = st.columns(2, gap="large")
with left:
    if not fires.empty:
        daily = fires.groupby("date").size().rename("focos").reset_index()
        figure = px.line(
            daily, x="date", y="focos", markers=True, title="Evolução diária dos focos",
            color_discrete_sequence=["#49e596"],
        )
        figure.update_layout(xaxis_title=None, yaxis_title="Focos")
        st.plotly_chart(style_figure(figure), width="stretch", config=PLOTLY_CONFIG)
    else:
        empty_state("Sem focos observados para a série diária.")

with right:
    if not fires.empty:
        monthly = fires.groupby("month").size().rename("focos").reset_index()
        figure = px.bar(
            monthly, x="month", y="focos", title="Quantidade mensal de focos",
            color="focos", color_continuous_scale=["#214936", "#ff7b3f"],
        )
        figure.update_layout(xaxis_title="Mês", yaxis_title="Focos", coloraxis_showscale=False)
        st.plotly_chart(style_figure(figure), width="stretch", config=PLOTLY_CONFIG)

municipalities = (
    fires.groupby("municipality").size().nlargest(12).index.tolist() if not fires.empty else []
)
selected_municipalities = st.multiselect(
    "Comparar municípios",
    sorted(fires["municipality"].dropna().unique()) if not fires.empty else [],
    default=municipalities[:5],
    max_selections=10,
)
if selected_municipalities:
    comparison = (
        fires[fires["municipality"].isin(selected_municipalities)]
        .groupby(["date", "municipality"]).size().rename("focos").reset_index()
    )
    figure = px.line(
        comparison,
        x="date",
        y="focos",
        color="municipality",
        markers=True,
        title="Comparação temporal entre municípios",
    )
    figure.update_layout(xaxis_title=None, yaxis_title="Focos", legend_title=None)
    st.plotly_chart(style_figure(figure, 430), width="stretch", config=PLOTLY_CONFIG)

st.markdown("#### Relação entre clima e focos")
if not weather.empty:
    weather_daily = weather.groupby(weather["observed_date"].dt.normalize(), as_index=False).agg(
        temperature_c=("temperature_c", "mean"),
        humidity_pct=("humidity_pct", "mean"),
        precipitation_mm=("precipitation_mm", "sum"),
    )
    weather_daily = weather_daily.rename(columns={"observed_date": "date"})
    if not fires.empty:
        fire_daily = fires.groupby("date").size().rename("focos").reset_index()
        combined = weather_daily.merge(fire_daily, on="date", how="left").fillna({"focos": 0})
    else:
        combined = weather_daily.assign(focos=0)

    temp_col, humidity_col = st.columns(2, gap="large")
    with temp_col:
        valid = combined.dropna(subset=["temperature_c"])
        figure = px.scatter(
            valid,
            x="temperature_c",
            y="focos",
            size="precipitation_mm",
            title="Temperatura média × focos diários",
            color="focos",
            color_continuous_scale=["#49e596", "#ff6548"],
            hover_data={"date": "|%d/%m/%Y", "precipitation_mm": ":.1f"},
        )
        figure.update_layout(xaxis_title="Temperatura média (°C)", yaxis_title="Focos")
        st.plotly_chart(style_figure(figure), width="stretch", config=PLOTLY_CONFIG)
    with humidity_col:
        valid = combined.dropna(subset=["humidity_pct"])
        figure = px.scatter(
            valid,
            x="humidity_pct",
            y="focos",
            title="Umidade média × focos diários",
            color="focos",
            color_continuous_scale=["#49e596", "#ff6548"],
            hover_data={"date": "|%d/%m/%Y"},
        )
        figure.update_layout(xaxis_title="Umidade média (%)", yaxis_title="Focos")
        st.plotly_chart(style_figure(figure), width="stretch", config=PLOTLY_CONFIG)
else:
    empty_state("A relação climática não pode ser calculada sem meteorologia válida.")

source_caption("Detecções: INPE Programa Queimadas", "Meteorologia: Open-Meteo")
