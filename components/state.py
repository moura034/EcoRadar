"""Estado global de filtros entre páginas."""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from config.settings import settings


def defaults() -> tuple[date, date]:
    end = pd.Timestamp.now(tz=ZoneInfo(settings.timezone)).date()
    return end - timedelta(days=6), end


def get_period() -> tuple[date, date]:
    start_default, end_default = defaults()
    start = st.session_state.get("ecoradar_start", start_default)
    end = st.session_state.get("ecoradar_end", end_default)
    return start, end
