"""Transparência do índice heurístico e do modelo supervisionado opcional."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from components.charts import PLOTLY_CONFIG, style_figure
from components.state import get_period
from components.ui import empty_state, format_number, hero, source_caption
from config.settings import settings
from models.risk_classifier import load_metrics
from services.dashboard_service import EcoRadarService


start, end = get_period()
bundle = EcoRadarService().load_bundle(start, end)
hero(
    "Inteligência de risco",
    "Metodologia transparente: índice heurístico operacional agora; classificador supervisionado somente após histórico suficiente e avaliação temporal.",
    "IA responsável • sem métricas fabricadas",
)

tab_heuristic, tab_model = st.tabs(["Índice heurístico", "Modelo supervisionado"])
with tab_heuristic:
    st.warning(
        "O índice EcoRadar v1 é uma heurística explicável. Ele não é uma previsão validada por inteligência artificial "
        "e não confirma incêndios."
    )
    weights = pd.DataFrame(
        {
            "Fator": ["Umidade baixa", "Temperatura", "Baixa precipitação", "Vento", "Histórico de focos", "Sazonalidade"],
            "Peso": [25, 20, 20, 15, 15, 5],
        }
    )
    figure = px.bar(
        weights.sort_values("Peso"),
        x="Peso",
        y="Fator",
        orientation="h",
        title="Composição máxima do índice (100 pontos)",
        color="Peso",
        color_continuous_scale=["#23503a", "#49e596"],
    )
    figure.update_layout(coloraxis_showscale=False, xaxis_title="Pontos máximos", yaxis_title=None)
    st.plotly_chart(style_figure(figure, 390), width="stretch", config=PLOTLY_CONFIG)
    st.markdown(
        """
        - Temperatura, umidade, vento e precipitação vêm da Open-Meteo.
        - Histórico considera detecções do INPE nos 30 dias anteriores.
        - Sazonalidade representa o ciclo seco regional declarado no código.
        - Se qualquer variável meteorológica essencial estiver ausente, o índice fica **Indisponível**.
        """
    )
    if not bundle.risk.empty:
        valid = bundle.risk.dropna(subset=["risk_score"])
        if not valid.empty:
            sample = valid.nlargest(15, "risk_score").sort_values("risk_score")
            figure = px.bar(
                sample,
                x="risk_score",
                y="municipality",
                orientation="h",
                title="Maiores índices no recorte atual",
                color="risk_score",
                color_continuous_scale=["#49e596", "#f3c94d", "#f04444"],
            )
            figure.update_layout(coloraxis_showscale=False, xaxis_title="Índice", yaxis_title=None)
            st.plotly_chart(style_figure(figure, 460), width="stretch", config=PLOTLY_CONFIG)

with tab_model:
    metrics = load_metrics()
    if not metrics:
        empty_state(
            "Nenhum modelo supervisionado validado está instalado.<br>Isso é esperado enquanto não houver histórico integrado suficiente. "
            "O EcoRadar não cria resultados ou métricas artificiais."
        )
        st.markdown("##### Como habilitar legitimamente")
        st.code(
            "python -m pipelines.spark_etl --start 2024-01-01 --end 2025-12-31\n"
            "python -m models.risk_classifier --input data/processed/municipality_daily.parquet",
            language="powershell",
        )
        st.caption(
            "O treinamento exige ao menos 2.000 linhas válidas, 30 dias distintos e presença das duas classes "
            "nos conjuntos temporalmente separados."
        )
    else:
        st.success("Modelo treinado e métricas persistidas a partir de dados reais.")
        cols = st.columns(5)
        cols[0].metric("Acurácia", format_number(metrics.get("accuracy"), 3))
        cols[1].metric("Precisão", format_number(metrics.get("precision"), 3))
        cols[2].metric("Recall", format_number(metrics.get("recall"), 3))
        cols[3].metric("F1-score", format_number(metrics.get("f1"), 3))
        cols[4].metric("ROC-AUC", format_number(metrics.get("roc_auc"), 3))
        st.caption(
            f"Treino: {metrics['train_start']} a {metrics['train_end']} ({metrics['train_rows']} linhas). "
            f"Teste: {metrics['test_start']} a {metrics['test_end']} ({metrics['test_rows']} linhas)."
        )
        matrix = metrics.get("confusion_matrix", [[0, 0], [0, 0]])
        figure = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=["Previsto: sem foco", "Previsto: com foco"],
                y=["Real: sem foco", "Real: com foco"],
                colorscale=[[0, "#10291c"], [1, "#49e596"]],
                text=matrix,
                texttemplate="%{text}",
            )
        )
        figure.update_layout(title="Matriz de confusão no teste temporal")
        st.plotly_chart(style_figure(figure, 390), width="stretch", config=PLOTLY_CONFIG)
        importances = pd.DataFrame(
            list(metrics.get("feature_importances", {}).items()), columns=["Variável", "Importância"]
        ).sort_values("Importância")
        figure = px.bar(importances, x="Importância", y="Variável", orientation="h", title="Importância das variáveis")
        st.plotly_chart(style_figure(figure, 420), width="stretch", config=PLOTLY_CONFIG)

source_caption("INPE", "Open-Meteo", "scikit-learn Random Forest")
