"""Treinamento temporal de classificador supervisionado de ocorrência futura.

O alvo é a existência de ao menos um foco observado pelo INPE no município no
dia seguinte. O artefato só é criado quando há histórico e classes suficientes;
nenhuma métrica é simulada quando os dados não atendem a esses critérios.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

from config.settings import settings


FEATURES = [
    "temperature_c",
    "humidity_pct",
    "wind_speed_kmh",
    "precipitation_mm",
    "fire_count_lag_1",
    "fire_count_7d",
    "fire_count_30d",
    "day_sin",
    "day_cos",
    "latitude",
    "longitude",
]


@dataclass(slots=True)
class TrainingMetrics:
    train_rows: int
    test_rows: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    confusion_matrix: list[list[int]]
    positive_rate_train: float
    positive_rate_test: float
    feature_importances: dict[str, float]


def prepare_training_data(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "municipality_id", "observed_date", "fire_count", "temperature_c", "humidity_pct",
        "wind_speed_kmh", "precipitation_mm", "latitude", "longitude",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Dados de treino sem colunas: {', '.join(sorted(missing))}")
    data = frame.copy()
    data["observed_date"] = pd.to_datetime(data["observed_date"], errors="coerce")
    data = data.dropna(subset=["observed_date", "municipality_id"]).sort_values(
        ["municipality_id", "observed_date"]
    )
    data["fire_count"] = pd.to_numeric(data["fire_count"], errors="coerce").fillna(0)
    grouped = data.groupby("municipality_id", group_keys=False)
    data["fire_count_lag_1"] = grouped["fire_count"].shift(1)
    data["fire_count_7d"] = grouped["fire_count"].transform(
        lambda values: values.shift(1).rolling(7, min_periods=1).sum()
    )
    data["fire_count_30d"] = grouped["fire_count"].transform(
        lambda values: values.shift(1).rolling(30, min_periods=7).sum()
    )
    future_fire = grouped["fire_count"].shift(-1)
    data["target_fire_next_day"] = (future_fire > 0).where(future_fire.notna(), pd.NA).astype("Int64")
    day_of_year = data["observed_date"].dt.day_of_year
    data["day_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    data["day_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    for feature in FEATURES:
        data[feature] = pd.to_numeric(data[feature], errors="coerce")
    return data.dropna(subset=FEATURES + ["target_fire_next_day"]).reset_index(drop=True)


def temporal_split(data: pd.DataFrame, test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = np.array(sorted(data["observed_date"].dt.normalize().unique()))
    if len(dates) < 30:
        raise ValueError("São necessários pelo menos 30 dias distintos para avaliação temporal.")
    split_index = max(1, min(len(dates) - 1, int(len(dates) * (1 - test_fraction))))
    split_date = pd.Timestamp(dates[split_index])
    train = data[data["observed_date"] < split_date].copy()
    test = data[data["observed_date"] >= split_date].copy()
    if train.empty or test.empty:
        raise ValueError("A divisão temporal produziu conjunto vazio.")
    return train, test


def train_classifier(
    data: pd.DataFrame,
    model_path: Path | None = None,
    metrics_path: Path | None = None,
) -> tuple[RandomForestClassifier, TrainingMetrics]:
    prepared = prepare_training_data(data)
    if len(prepared) < 2_000:
        raise ValueError(
            f"Histórico insuficiente: {len(prepared)} linhas válidas; mínimo configurado: 2.000. "
            "O dashboard continuará usando somente o índice heurístico identificado."
        )
    train, test = temporal_split(prepared)
    y_train = train["target_fire_next_day"].astype(int)
    y_test = test["target_fire_next_day"].astype(int)
    if y_train.nunique() < 2 or y_test.nunique() < 2:
        raise ValueError("Treino e teste precisam conter dias com e sem focos para métricas honestas.")

    model = RandomForestClassifier(
        n_estimators=350,
        max_depth=16,
        min_samples_leaf=4,
        class_weight="balanced_subsample",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(train[FEATURES], y_train)
    predictions = model.predict(test[FEATURES])
    probabilities = model.predict_proba(test[FEATURES])[:, 1]
    metrics = TrainingMetrics(
        train_rows=len(train),
        test_rows=len(test),
        train_start=train["observed_date"].min().date().isoformat(),
        train_end=train["observed_date"].max().date().isoformat(),
        test_start=test["observed_date"].min().date().isoformat(),
        test_end=test["observed_date"].max().date().isoformat(),
        accuracy=float(accuracy_score(y_test, predictions)),
        precision=float(precision_score(y_test, predictions, zero_division=0)),
        recall=float(recall_score(y_test, predictions, zero_division=0)),
        f1=float(f1_score(y_test, predictions, zero_division=0)),
        roc_auc=float(roc_auc_score(y_test, probabilities)) if y_test.nunique() == 2 else None,
        confusion_matrix=confusion_matrix(y_test, predictions, labels=[0, 1]).tolist(),
        positive_rate_train=float(y_train.mean()),
        positive_rate_test=float(y_test.mean()),
        feature_importances={
            feature: float(importance)
            for feature, importance in zip(FEATURES, model.feature_importances_, strict=True)
        },
    )

    model_path = model_path or settings.model_dir / "risk_classifier.joblib"
    metrics_path = metrics_path or settings.model_dir / "risk_classifier_metrics.json"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "features": FEATURES,
            "trained_until": metrics.train_end,
            "target": "ocorrência de ao menos um foco INPE no dia seguinte",
        },
        model_path,
    )
    metrics_path.write_text(json.dumps(asdict(metrics), ensure_ascii=False, indent=2), encoding="utf-8")
    return model, metrics


def load_model(path: Path | None = None) -> dict[str, Any] | None:
    artifact = path or settings.model_dir / "risk_classifier.joblib"
    return joblib.load(artifact) if artifact.exists() else None


def load_metrics(path: Path | None = None) -> dict[str, Any] | None:
    artifact = path or settings.model_dir / "risk_classifier_metrics.json"
    return json.loads(artifact.read_text(encoding="utf-8")) if artifact.exists() else None


def _read_input(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Treina o classificador temporal do EcoRadar.")
    parser.add_argument("--input", type=Path, default=settings.processed_dir / "municipality_daily.parquet")
    parser.add_argument("--model", type=Path, default=settings.model_dir / "risk_classifier.joblib")
    parser.add_argument("--metrics", type=Path, default=settings.model_dir / "risk_classifier_metrics.json")
    args = parser.parse_args()
    frame = _read_input(args.input)
    _, metrics = train_classifier(frame, args.model, args.metrics)
    print(json.dumps(asdict(metrics), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
