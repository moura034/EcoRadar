"""Orquestra fontes, persistência, risco e visões do dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pandas as pd

from config.settings import settings
from database.db import EcoRadarDatabase
from models.risk_index import calculate_risk_index, explain_risk
from services.ibge_service import IBGEService
from services.inpe_service import INPEService
from services.weather_service import WeatherService


@dataclass(slots=True)
class SynchronizationReport:
    started_for: tuple[date, date]
    counts: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def successful(self) -> bool:
        return any(value > 0 for value in self.counts.values())


@dataclass(slots=True)
class DashboardBundle:
    municipalities: pd.DataFrame
    fire_spots: pd.DataFrame
    weather: pd.DataFrame
    risk: pd.DataFrame
    ranking: pd.DataFrame
    alerts: pd.DataFrame
    source_updates: pd.DataFrame

    @property
    def has_observations(self) -> bool:
        return not self.fire_spots.empty or not self.weather.empty


class EcoRadarService:
    def __init__(
        self,
        database: EcoRadarDatabase | None = None,
        ibge: IBGEService | None = None,
        inpe: INPEService | None = None,
        weather: WeatherService | None = None,
    ) -> None:
        self.database = database or EcoRadarDatabase()
        self.ibge = ibge or IBGEService()
        self.inpe = inpe or INPEService()
        self.weather = weather or WeatherService()

    def _municipalities(self, refresh: bool = False) -> tuple[pd.DataFrame, list[str]]:
        cached = self.database.municipalities()
        if not refresh and len(cached) == 224:
            cached["geometry"] = cached["geometry_json"].map(
                lambda value: json.loads(value) if value else None
            )
            return cached, []
        result = self.ibge.fetch_municipalities()
        if result.available:
            self.database.upsert_municipalities(result.data)
            self.database.record_source_update(
                "IBGE",
                "Disponível",
                len(result.data),
                message="Municípios e malhas oficiais do Piauí atualizados.",
                metadata=result.metadata,
            )
            return result.data, result.issues
        self.database.record_source_update(
            "IBGE", "Indisponível", 0, message="; ".join(result.issues), metadata=result.metadata
        )
        if not cached.empty:
            cached["geometry"] = cached["geometry_json"].map(
                lambda value: json.loads(value) if value else None
            )
            return cached, result.issues + ["Foi mantido o último cadastro IBGE salvo localmente."]
        return result.data, result.issues

    def synchronize(self, start: date, end: date, refresh_ibge: bool = False) -> SynchronizationReport:
        if end < start:
            raise ValueError("A data final deve ser igual ou posterior à data inicial.")
        days = (end - start).days + 1
        if days > settings.max_live_days:
            raise ValueError(
                f"A sincronização interativa é limitada a {settings.max_live_days} dias. "
                "Use o pipeline PySpark ou importe os ZIPs anuais do INPE para períodos maiores."
            )

        report = SynchronizationReport(started_for=(start, end))
        municipalities, ibge_issues = self._municipalities(refresh=refresh_ibge)
        report.counts["municipalities"] = len(municipalities)
        report.issues.extend(ibge_issues)
        if municipalities.empty:
            report.issues.append("Sincronização interrompida: municípios do IBGE indisponíveis.")
            return report

        fire_result = self.inpe.fetch_daily(start, end)
        report.issues.extend(fire_result.issues)
        report.metadata["inpe"] = fire_result.metadata
        report.counts["fire_spots"] = self.database.upsert_fire_spots(fire_result.data)
        self.database.record_source_update(
            "INPE",
            "Disponível" if fire_result.available else "Sem dados no período",
            len(fire_result.data),
            start.isoformat(),
            end.isoformat(),
            "; ".join(fire_result.issues) or "Arquivos oficiais diários processados.",
            fire_result.metadata,
        )

        weather_result = self.weather.fetch_daily(municipalities, start, end)
        report.issues.extend(weather_result.issues)
        report.metadata["weather"] = weather_result.metadata
        report.counts["weather_rows"] = self.database.upsert_weather(weather_result.data)
        self.database.record_source_update(
            "Open-Meteo",
            "Disponível" if weather_result.available else "Indisponível",
            len(weather_result.data),
            start.isoformat(),
            end.isoformat(),
            "; ".join(weather_result.issues) or "Meteorologia diária processada.",
            weather_result.metadata,
        )

        risk = self.calculate_current_risk(municipalities, end)
        report.counts["risk_rows"] = self.database.upsert_risk_snapshots(risk)
        alert_candidates = risk[
            risk["risk_is_valid"] & risk["risk_class"].isin(["Alto", "Crítico"])
        ].copy()
        report.counts["alerts"] = self.database.create_alerts(alert_candidates)
        return report

    def calculate_current_risk(self, municipalities: pd.DataFrame, reference_date: date) -> pd.DataFrame:
        weather_start = reference_date - timedelta(days=6)
        fires_start = reference_date - timedelta(days=29)
        weather = self.database.weather(weather_start.isoformat(), reference_date.isoformat())
        fires = self.database.fire_spots(fires_start.isoformat(), reference_date.isoformat())

        base = municipalities.rename(columns={"ibge_code": "municipality_id", "name": "municipality"})[
            ["municipality_id", "municipality", "latitude", "longitude"]
        ].copy()
        if not weather.empty:
            weather_agg = weather.groupby("municipality_id", as_index=False).agg(
                temperature_c=("temperature_c", "mean"),
                humidity_pct=("humidity_pct", "mean"),
                wind_speed_kmh=("wind_speed_kmh", "mean"),
                wind_direction_deg=("wind_direction_deg", "mean"),
                precipitation_mm=("precipitation_mm", "sum"),
            )
            base = base.merge(weather_agg, on="municipality_id", how="left")
        else:
            for column in (
                "temperature_c", "humidity_pct", "wind_speed_kmh",
                "wind_direction_deg", "precipitation_mm",
            ):
                base[column] = pd.NA

        if not fires.empty:
            counts = fires.groupby("municipality_id").size().rename("fire_count_30d").reset_index()
            base = base.merge(counts, on="municipality_id", how="left")
        else:
            base["fire_count_30d"] = 0
        base["fire_count_30d"] = base["fire_count_30d"].fillna(0)
        base["month"] = reference_date.month
        risk = calculate_risk_index(base)
        risk["observed_date"] = reference_date.isoformat()
        risk["factors"] = risk.apply(explain_risk, axis=1)
        risk["source_summary"] = (
            "Meteorologia: Open-Meteo; focos observados: INPE; municípios: IBGE; "
            "método: índice heurístico EcoRadar v1 (não é previsão validada por IA)."
        )
        return risk

    def load_bundle(self, start: date, end: date) -> DashboardBundle:
        municipalities = self.database.municipalities()
        fire_spots = self.database.fire_spots(start.isoformat(), end.isoformat())
        weather = self.database.weather(start.isoformat(), end.isoformat())
        risk = self.database.latest_risk(start.isoformat(), end.isoformat())
        alerts = self.database.alerts(start.isoformat(), end.isoformat())
        source_updates = self.database.source_updates()
        ranking = self._build_ranking(municipalities, fire_spots, weather, risk)
        return DashboardBundle(
            municipalities=municipalities,
            fire_spots=fire_spots,
            weather=weather,
            risk=risk,
            ranking=ranking,
            alerts=alerts,
            source_updates=source_updates,
        )

    @staticmethod
    def _build_ranking(
        municipalities: pd.DataFrame,
        fires: pd.DataFrame,
        weather: pd.DataFrame,
        risk: pd.DataFrame,
    ) -> pd.DataFrame:
        if municipalities.empty:
            return pd.DataFrame()
        ranking = municipalities.rename(columns={"ibge_code": "municipality_id", "name": "municipality"})[
            ["municipality_id", "municipality", "latitude", "longitude"]
        ].copy()
        if not fires.empty:
            counts = fires.groupby("municipality_id").size().rename("fire_count").reset_index()
            ranking = ranking.merge(counts, on="municipality_id", how="left")
        ranking["fire_count"] = ranking.get("fire_count", 0)
        ranking["fire_count"] = ranking["fire_count"].fillna(0).astype(int)

        if not weather.empty:
            weather_agg = weather.groupby("municipality_id", as_index=False).agg(
                temperature_c=("temperature_c", "mean"),
                humidity_pct=("humidity_pct", "mean"),
                wind_speed_kmh=("wind_speed_kmh", "mean"),
                precipitation_mm=("precipitation_mm", "sum"),
            )
            ranking = ranking.merge(weather_agg, on="municipality_id", how="left")
        if not risk.empty:
            risk_columns = ["municipality_id", "risk_score", "risk_class", "risk_method", "factors_json"]
            ranking = ranking.merge(risk[risk_columns], on="municipality_id", how="left")
        for column in ("risk_score", "risk_class", "risk_method", "factors_json"):
            if column not in ranking:
                ranking[column] = pd.NA
        ranking["risk_class"] = ranking["risk_class"].fillna("Indisponível")
        ranking = ranking.sort_values(["risk_score", "fire_count"], ascending=[False, False], na_position="last")
        ranking.insert(0, "position", range(1, len(ranking) + 1))
        return ranking.reset_index(drop=True)
