"""Índice heurístico transparente para risco ambiental de incêndio.

Este módulo não se apresenta como previsão validada por IA. Ele combina variáveis
ambientais em uma escala de 0 a 100 e explica cada contribuição.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


RISK_COLORS = {
    "Baixo": "#27c277",
    "Moderado": "#f3c94d",
    "Alto": "#ff8b3d",
    "Crítico": "#f04444",
    "Indisponível": "#6b7280",
}


@dataclass(frozen=True, slots=True)
class RiskThresholds:
    moderate: float = 30.0
    high: float = 55.0
    critical: float = 75.0


def classify_risk(score: float | int | None, thresholds: RiskThresholds | None = None) -> str:
    thresholds = thresholds or RiskThresholds()
    if score is None or pd.isna(score):
        return "Indisponível"
    numeric = float(score)
    if numeric >= thresholds.critical:
        return "Crítico"
    if numeric >= thresholds.high:
        return "Alto"
    if numeric >= thresholds.moderate:
        return "Moderado"
    return "Baixo"


def _clip(value: pd.Series | float, lower: float = 0.0, upper: float = 1.0):
    return np.clip(value, lower, upper)


def seasonal_factor(month: pd.Series | int) -> pd.Series | float:
    """Sazonalidade aproximada do Piauí; pesos são declarativos, não treinados."""
    values = {
        1: 0.15,
        2: 0.10,
        3: 0.08,
        4: 0.12,
        5: 0.30,
        6: 0.55,
        7: 0.75,
        8: 0.95,
        9: 1.00,
        10: 0.90,
        11: 0.65,
        12: 0.35,
    }
    if isinstance(month, pd.Series):
        return month.map(values).fillna(0.0)
    return values.get(int(month), 0.0)


def calculate_risk_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Calcula índice e contribuições; exige as quatro variáveis meteorológicas.

    Colunas esperadas: temperature_c, humidity_pct, wind_speed_kmh,
    precipitation_mm, fire_count_30d e month. Valores meteorológicos ausentes
    tornam o risco indisponível, evitando apresentar números sem base válida.
    """
    result = frame.copy()
    required_weather = [
        "temperature_c",
        "humidity_pct",
        "wind_speed_kmh",
        "precipitation_mm",
    ]
    for column in required_weather + ["fire_count_30d", "month"]:
        if column not in result:
            result[column] = np.nan if column in required_weather else 0
        result[column] = pd.to_numeric(result[column], errors="coerce")

    valid = result[required_weather].notna().all(axis=1)
    fire_history = result["fire_count_30d"].fillna(0).clip(lower=0)
    month = result["month"].fillna(pd.Timestamp.now().month).astype(int)

    result["factor_temperature"] = _clip((result["temperature_c"] - 20.0) / 20.0)
    result["factor_humidity"] = _clip((70.0 - result["humidity_pct"]) / 50.0)
    result["factor_wind"] = _clip(result["wind_speed_kmh"] / 40.0)
    result["factor_precipitation"] = _clip((10.0 - result["precipitation_mm"]) / 10.0)
    result["factor_fire_history"] = _clip(np.log1p(fire_history) / np.log(11.0))
    result["factor_seasonality"] = seasonal_factor(month)

    contributions = {
        "temperature": ("factor_temperature", 20.0),
        "humidity": ("factor_humidity", 25.0),
        "wind": ("factor_wind", 15.0),
        "precipitation": ("factor_precipitation", 20.0),
        "fire_history": ("factor_fire_history", 15.0),
        "seasonality": ("factor_seasonality", 5.0),
    }
    score = pd.Series(0.0, index=result.index)
    for name, (factor_column, weight) in contributions.items():
        contribution_column = f"contribution_{name}"
        result[contribution_column] = result[factor_column] * weight
        score += result[contribution_column].fillna(0.0)

    result["risk_score"] = score.round(1).where(valid)
    result["risk_class"] = result["risk_score"].map(classify_risk)
    result["risk_method"] = np.where(valid, "Índice heurístico EcoRadar v1", "Indisponível")
    result["risk_is_valid"] = valid
    return result


def explain_risk(row: pd.Series | dict[str, Any], limit: int = 3) -> list[str]:
    values = row if isinstance(row, dict) else row.to_dict()
    labels = {
        "contribution_temperature": "temperatura elevada",
        "contribution_humidity": "umidade baixa",
        "contribution_wind": "vento intenso",
        "contribution_precipitation": "baixa precipitação",
        "contribution_fire_history": "histórico recente de focos",
        "contribution_seasonality": "sazonalidade",
    }
    ranked = []
    for key, label in labels.items():
        value = values.get(key)
        if value is not None and not pd.isna(value):
            ranked.append((float(value), label))
    return [label for value, label in sorted(ranked, reverse=True)[:limit] if value > 0]
