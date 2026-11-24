"""Mapa municipal de risco e focos observados."""

from __future__ import annotations

import json

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from components.state import get_period
from components.ui import empty_state, hero, source_caption
from models.risk_index import RISK_COLORS
from services.dashboard_service import EcoRadarService


start, end = get_period()
bundle = EcoRadarService().load_bundle(start, end)
hero(
    "Mapa inteligente de risco",
    "Compare a camada municipal estimada com as detecções pontuais do INPE. Passe o cursor ou clique para consultar detalhes.",
    f"Mapa • {start:%d/%m/%Y} a {end:%d/%m/%Y}",
)

if bundle.municipalities.empty:
    empty_state("A malha municipal ainda não foi baixada. Sincronize as fontes oficiais no menu lateral.")
    st.stop()

municipality_options = ["Todos"] + bundle.municipalities["name"].tolist()
filter_col, layer_col, info_col = st.columns((1.3, 1, 1))
with filter_col:
    selected = st.selectbox("Município", municipality_options)
with layer_col:
    show_fires = st.toggle("Focos observados", value=True)
with info_col:
    st.metric("Focos exibidos", len(bundle.fire_spots))

risk_lookup = {}
if not bundle.risk.empty:
    for row in bundle.risk.itertuples():
        risk_lookup[int(row.municipality_id)] = {
            "risk_score": None if pd.isna(row.risk_score) else float(row.risk_score),
            "risk_class": row.risk_class,
        }

features = []
selected_code = None
if selected != "Todos":
    selected_row = bundle.municipalities[bundle.municipalities["name"] == selected].iloc[0]
    selected_code = int(selected_row["ibge_code"])

for row in bundle.municipalities.itertuples():
    if selected_code and int(row.ibge_code) != selected_code:
        continue
    geometry = json.loads(row.geometry_json) if row.geometry_json else None
    if not geometry:
        continue
    risk_info = risk_lookup.get(int(row.ibge_code), {"risk_score": None, "risk_class": "Indisponível"})
    score_label = "Sem dados" if risk_info["risk_score"] is None else f"{risk_info['risk_score']:.1f}/100"
    features.append(
        {
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "ibge_code": int(row.ibge_code),
                "municipality": row.name,
                "risk_class": risk_info["risk_class"],
                "risk_score_label": score_label,
                "color": RISK_COLORS.get(risk_info["risk_class"], "#6b7280"),
            },
        }
    )

geojson = {"type": "FeatureCollection", "features": features}
center = [-7.25, -42.35]
zoom = 6.2
if selected_code:
    row = bundle.municipalities[bundle.municipalities["ibge_code"] == selected_code].iloc[0]
    center = [row["latitude"], row["longitude"]]
    zoom = 9

map_object = folium.Map(
    location=center,
    zoom_start=zoom,
    tiles="OpenStreetMap",
    control_scale=True,
    prefer_canvas=True,
)
folium.GeoJson(
    geojson,
    name="Risco estimado por município",
    style_function=lambda feature: {
        "fillColor": feature["properties"]["color"],
        "color": "#c8ddd2",
        "weight": 0.7,
        "fillOpacity": 0.48,
    },
    highlight_function=lambda _: {"weight": 2.2, "fillOpacity": 0.72, "color": "#ffffff"},
    tooltip=folium.GeoJsonTooltip(
        fields=["municipality", "risk_class", "risk_score_label"],
        aliases=["Município", "Classificação", "Índice"],
        sticky=True,
    ),
    popup=folium.GeoJsonPopup(
        fields=["municipality", "ibge_code", "risk_class", "risk_score_label"],
        aliases=["Município", "Código IBGE", "Risco", "Índice"],
    ),
).add_to(map_object)

fires = bundle.fire_spots.copy()
if selected_code and not fires.empty:
    fires = fires[fires["municipality_id"] == selected_code]
if show_fires and not fires.empty:
    cluster = MarkerCluster(name="Focos observados (INPE)", disableClusteringAtZoom=10).add_to(map_object)
    marker_limit = 5_000
    for row in fires.head(marker_limit).itertuples():
        observed = pd.to_datetime(row.observed_at, errors="coerce")
        popup = (
            f"<b>Foco observado pelo INPE</b><br>{row.municipality}<br>"
            f"{observed:%d/%m/%Y %H:%M} UTC<br>Satélite: {row.satellite}"
        )
        folium.CircleMarker(
            [row.latitude, row.longitude],
            radius=4,
            color="#ffad55",
            weight=1,
            fill=True,
            fill_color="#ff5c35",
            fill_opacity=.78,
            popup=folium.Popup(popup, max_width=290),
            tooltip=f"Foco INPE • {row.municipality}",
        ).add_to(cluster)
    if len(fires) > marker_limit:
        st.info(f"O mapa mostra os primeiros {marker_limit:,} focos para preservar o desempenho.")

folium.LayerControl(collapsed=False).add_to(map_object)
st_folium(map_object, width=None, height=660, returned_objects=[])

legend = " ".join(
    f'<span style="color:{color};margin-right:14px">● {label}</span>'
    for label, color in RISK_COLORS.items()
    if label != "Indisponível"
)
st.markdown(legend, unsafe_allow_html=True)
source_caption("Malhas municipais: IBGE", "Focos: INPE", "Risco: índice heurístico EcoRadar")
