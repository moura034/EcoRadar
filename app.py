"""Entrada principal da aplicação Streamlit EcoRadar."""

from __future__ import annotations

import streamlit as st

from components.state import defaults
from components.ui import inject_styles, logo_path, render_brand
from config.settings import settings
from database.db import EcoRadarDatabase
from services.dashboard_service import EcoRadarService


st.set_page_config(
    page_title="EcoRadar • Monitoramento Ambiental",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="auto",
)
inject_styles()
try:
    st.logo(str(logo_path()), size="large")
except TypeError:  # compatibilidade com versões anteriores do Streamlit
    st.logo(str(logo_path()))

start_default, end_default = defaults()
with st.sidebar:
    render_brand()
    st.markdown("#### Período de análise")
    start = st.date_input(
        "Data inicial",
        value=st.session_state.get("ecoradar_start", start_default),
        max_value=end_default,
        format="DD/MM/YYYY",
    )
    end = st.date_input(
        "Data final",
        value=st.session_state.get("ecoradar_end", end_default),
        max_value=end_default,
        format="DD/MM/YYYY",
    )
    st.session_state["ecoradar_start"] = start
    st.session_state["ecoradar_end"] = end
    if end < start:
        st.error("A data final deve ser posterior à inicial.")
    sync = st.button("Sincronizar fontes oficiais", type="primary", width="stretch")
    if sync and end >= start:
        try:
            with st.spinner("Consultando INPE, IBGE e Open-Meteo…"):
                report = EcoRadarService().synchronize(start, end)
            st.session_state["last_sync_report"] = report
            if report.successful:
                st.success("Dados atualizados.")
            else:
                st.warning("Nenhuma fonte retornou registros novos.")
            for issue in report.issues[:4]:
                st.warning(issue)
        except Exception as exc:
            st.error(f"Não foi possível sincronizar: {exc}")

    updates = EcoRadarDatabase().source_updates()
    with st.expander("Estado das fontes", expanded=False):
        if updates.empty:
            st.caption("Nenhuma sincronização realizada neste computador.")
        else:
            for row in updates.itertuples():
                icon = "●" if row.status == "Disponível" else "○"
                st.markdown(f"{icon} **{row.source}** — {row.status}")
                st.caption(f"{row.records_count} registros • {row.updated_at}")
    st.caption("Dados observados e estimativas são identificados separadamente.")

pages = {
    "Monitoramento": [
        st.Page("views/dashboard.py", title="Visão geral", icon=":material/space_dashboard:"),
        st.Page("views/mapa.py", title="Mapa interativo", icon=":material/map:"),
        st.Page("views/municipios.py", title="Ranking municipal", icon=":material/leaderboard:"),
        st.Page("views/historico.py", title="Análise temporal", icon=":material/timeline:"),
    ],
    "Inteligência": [
        st.Page("views/inteligencia_artificial.py", title="Inteligência artificial", icon=":material/model_training:"),
        st.Page("views/alertas.py", title="Central de alertas", icon=":material/notifications_active:"),
    ],
}
navigation = st.navigation(pages)
navigation.run()
