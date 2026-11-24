"""Configuração coerente dos gráficos Plotly."""

from __future__ import annotations

import plotly.graph_objects as go


PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "responsive": True,
}


def style_figure(figure: go.Figure, height: int = 360) -> go.Figure:
    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=54, b=28),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,20,14,.35)",
        font=dict(color="#dcebe3", family="Inter, Segoe UI, sans-serif"),
        title_font=dict(size=17),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor="#10241a", font_color="#effaf3"),
    )
    figure.update_xaxes(gridcolor="rgba(148,180,160,.08)", zeroline=False)
    figure.update_yaxes(gridcolor="rgba(148,180,160,.08)", zeroline=False)
    return figure
