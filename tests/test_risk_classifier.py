import pandas as pd

from models.risk_classifier import prepare_training_data, temporal_split


def _history():
    rows = []
    for municipality_id in (1, 2):
        for index, observed_date in enumerate(pd.date_range("2025-01-01", periods=45)):
            rows.append(
                {
                    "municipality_id": municipality_id,
                    "observed_date": observed_date,
                    "fire_count": 1 if index % 6 == 0 else 0,
                    "temperature_c": 30 + index % 4,
                    "humidity_pct": 45,
                    "wind_speed_kmh": 14,
                    "precipitation_mm": 0,
                    "latitude": -5.0,
                    "longitude": -42.0,
                }
            )
    return pd.DataFrame(rows)


def test_features_use_only_previous_fire_counts():
    source = _history()
    prepared = prepare_training_data(source)
    municipality = prepared[prepared["municipality_id"] == 1].sort_values("observed_date")
    first = municipality.iloc[0]
    previous_date = first["observed_date"] - pd.Timedelta(days=1)
    previous_count = source[
        (source["municipality_id"] == 1) & (source["observed_date"] == previous_date)
    ].iloc[0]["fire_count"]
    assert first["fire_count_lag_1"] == previous_count
    assert municipality.iloc[-1]["observed_date"] < pd.Timestamp("2025-02-14")


def test_temporal_split_never_mixes_future_into_train():
    prepared = prepare_training_data(_history())
    train, test = temporal_split(prepared)
    assert train["observed_date"].max() < test["observed_date"].min()
