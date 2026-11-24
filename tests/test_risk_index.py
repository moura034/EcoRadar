import numpy as np
import pandas as pd

from models.risk_index import calculate_risk_index, classify_risk, explain_risk


def test_classification_thresholds():
    assert classify_risk(None) == "Indisponível"
    assert classify_risk(0) == "Baixo"
    assert classify_risk(30) == "Moderado"
    assert classify_risk(55) == "Alto"
    assert classify_risk(75) == "Crítico"


def test_risk_is_bounded_and_explainable():
    frame = pd.DataFrame(
        [
            {
                "temperature_c": 38,
                "humidity_pct": 22,
                "wind_speed_kmh": 30,
                "precipitation_mm": 0,
                "fire_count_30d": 8,
                "month": 9,
            }
        ]
    )
    result = calculate_risk_index(frame).iloc[0]
    assert 0 <= result["risk_score"] <= 100
    assert result["risk_is_valid"]
    assert result["risk_class"] in {"Alto", "Crítico"}
    assert len(explain_risk(result)) == 3


def test_missing_weather_makes_risk_unavailable():
    frame = pd.DataFrame(
        [{
            "temperature_c": 34,
            "humidity_pct": np.nan,
            "wind_speed_kmh": 12,
            "precipitation_mm": 1,
            "fire_count_30d": 2,
            "month": 8,
        }]
    )
    result = calculate_risk_index(frame).iloc[0]
    assert pd.isna(result["risk_score"])
    assert result["risk_class"] == "Indisponível"
    assert not result["risk_is_valid"]
