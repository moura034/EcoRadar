"""Identidade visual e componentes reutilizáveis."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from config.settings import BASE_DIR, settings


LOGO_PATH = BASE_DIR / "assets" / "ecoradar-logo.svg"


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root { --eco:#49e596; --bg:#07110d; --panel:#0e1b16; --muted:#92a49b; }
        [data-testid="stAppViewContainer"] { background:
          radial-gradient(circle at 85% -10%, rgba(37,187,115,.12), transparent 34%), #07110d; }
        [data-testid="stSidebar"] { background:#091610; border-right:1px solid rgba(116,231,171,.10); }
        [data-testid="stSidebarNav"] span { font-weight:540; }
        .block-container { max-width:1480px; padding-top:2rem; padding-bottom:4rem; }
        h1,h2,h3 { letter-spacing:-.025em; }
        h1 { font-size:2.15rem !important; }
        [data-testid="stMetric"] { background:linear-gradient(145deg,rgba(17,35,27,.96),rgba(11,25,19,.96));
          border:1px solid rgba(113,219,161,.12); border-radius:16px; padding:16px 17px; min-height:126px; }
        [data-testid="stMetric"] label { color:#9cb0a5; font-weight:600; }
        [data-testid="stMetricValue"] { color:#f3fbf6; font-weight:720; }
        .eco-hero { position:relative; overflow:hidden; border:1px solid rgba(94,229,155,.15); border-radius:22px;
          padding:28px 30px; margin-bottom:22px; background:linear-gradient(125deg,#0d2017 0%,#0a1812 62%,#11251b 100%); }
        .eco-hero:after { content:""; position:absolute; width:260px; height:260px; right:-78px; top:-100px;
          border:1px solid rgba(76,233,149,.20); border-radius:50%; box-shadow:0 0 0 34px rgba(76,233,149,.035),0 0 0 72px rgba(76,233,149,.025); }
        .eco-eyebrow { color:#58e89c; text-transform:uppercase; letter-spacing:.14em; font-size:.74rem; font-weight:750; }
        .eco-hero h1 { margin:.45rem 0 .5rem; font-size:2.35rem !important; }
        .eco-hero p { margin:0; color:#9fb1a7; max-width:760px; font-size:1rem; }
        .eco-section { color:#a9bbb1; font-size:.82rem; text-transform:uppercase; letter-spacing:.1em;
          font-weight:700; margin-top:1.5rem; margin-bottom:.55rem; }
        .eco-note { border-left:3px solid #49e596; background:rgba(31,84,57,.18); padding:12px 15px;
          border-radius:0 10px 10px 0; color:#b8c9c0; font-size:.9rem; }
        .eco-empty { border:1px dashed rgba(137,168,151,.28); border-radius:18px; padding:32px;
          text-align:center; color:#aab9b1; background:rgba(13,28,20,.55); }
        .risk-pill { display:inline-flex; align-items:center; gap:.4rem; border-radius:999px; padding:.24rem .62rem;
          font-size:.78rem; font-weight:700; border:1px solid currentColor; }
        div[data-testid="stDataFrame"] { border:1px solid rgba(117,216,160,.10); border-radius:14px; overflow:hidden; }
        div[data-testid="stPlotlyChart"] { border:1px solid rgba(117,216,160,.08); border-radius:16px; overflow:hidden; }
        .stButton>button { border-radius:10px; font-weight:650; }
        .stButton>button[kind="primary"] { color:#062014; }
        code { color:#79efad !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_brand() -> None:
    st.image(str(LOGO_PATH), width="stretch")
    st.caption("Monitoramento ambiental do Piauí")


def hero(title: str, description: str, eyebrow: str = "EcoRadar • Piauí") -> None:
    st.markdown(
        f"""
        <div class="eco-hero">
          <div class="eco-eyebrow">{eyebrow}</div>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_label(label: str) -> None:
    st.markdown(f'<div class="eco-section">{label}</div>', unsafe_allow_html=True)


def empty_state(message: str) -> None:
    st.markdown(f'<div class="eco-empty">{message}</div>', unsafe_allow_html=True)


def source_caption(*sources: str) -> None:
    available = [source for source in sources if source]
    if available:
        st.caption("Fontes: " + " • ".join(available))


def format_number(value, decimals: int = 0, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        if value != value:
            return "—"
        formatted = f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{formatted}{suffix}"
    except (TypeError, ValueError):
        return "—"


def logo_path() -> Path:
    return LOGO_PATH
