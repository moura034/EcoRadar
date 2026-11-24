"""Dados meteorológicos complementares da Open-Meteo."""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

from config.settings import settings
from services.base import ServiceResult, build_http_session
from utils.helpers import chunked


DAILY_VARIABLES = [
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "wind_speed_10m_max",
    "wind_direction_10m_dominant",
    "precipitation_sum",
]


class WeatherService:
    source_name = "Open-Meteo"

    def __init__(self, session=None) -> None:
        self.session = session or build_http_session()
        self.raw_dir = settings.raw_dir / "weather"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _endpoint(end: date) -> tuple[str, str]:
        today = pd.Timestamp.now(tz=ZoneInfo(settings.timezone)).date()
        if end <= today - timedelta(days=5):
            return settings.open_meteo_archive_url, "Open-Meteo Historical Weather API"
        return settings.open_meteo_forecast_url, "Open-Meteo Forecast API"

    def fetch_daily(self, municipalities: pd.DataFrame, start: date, end: date) -> ServiceResult:
        required = {"ibge_code", "name", "latitude", "longitude"}
        if not required.issubset(municipalities.columns):
            missing = ", ".join(sorted(required - set(municipalities.columns)))
            return ServiceResult(issues=[f"Municípios sem campos necessários à meteorologia: {missing}"])

        clean = municipalities.dropna(subset=["latitude", "longitude"]).copy()
        if clean.empty:
            return ServiceResult(issues=["Nenhum município possui coordenadas válidas para consulta meteorológica."])

        endpoint, source_detail = self._endpoint(end)
        records: list[dict] = []
        issues: list[str] = []
        for batch in chunked(clean.to_dict(orient="records"), 40):
            params = {
                "latitude": ",".join(f"{item['latitude']:.5f}" for item in batch),
                "longitude": ",".join(f"{item['longitude']:.5f}" for item in batch),
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "daily": ",".join(DAILY_VARIABLES),
                "timezone": settings.timezone,
                "wind_speed_unit": "kmh",
            }
            try:
                response = self.session.get(endpoint, params=params, timeout=settings.request_timeout_seconds)
                response.raise_for_status()
                payload = response.json()
                payloads = payload if isinstance(payload, list) else [payload]
                if len(payloads) != len(batch):
                    raise ValueError(
                        f"resposta contém {len(payloads)} locais para lote de {len(batch)} municípios"
                    )
                for municipality, location in zip(batch, payloads, strict=True):
                    daily = location.get("daily", {})
                    times = daily.get("time", [])
                    for index, observed_date in enumerate(times):
                        def value(field: str):
                            values = daily.get(field, [])
                            return values[index] if index < len(values) else None

                        records.append(
                            {
                                "municipality_id": int(municipality["ibge_code"]),
                                "municipality": municipality["name"],
                                "observed_date": observed_date,
                                "temperature_c": value("temperature_2m_mean"),
                                "humidity_pct": value("relative_humidity_2m_mean"),
                                "wind_speed_kmh": value("wind_speed_10m_max"),
                                "wind_direction_deg": value("wind_direction_10m_dominant"),
                                "precipitation_mm": value("precipitation_sum"),
                                "latitude": location.get("latitude", municipality["latitude"]),
                                "longitude": location.get("longitude", municipality["longitude"]),
                                "source": source_detail,
                            }
                        )
            except Exception as exc:
                first = batch[0]["name"]
                last = batch[-1]["name"]
                issues.append(f"Open-Meteo indisponível no lote {first}–{last}: {exc}")

        frame = pd.DataFrame(records)
        if not frame.empty:
            frame["observed_date"] = pd.to_datetime(frame["observed_date"])
            for column in ("temperature_c", "humidity_pct", "wind_speed_kmh", "wind_direction_deg", "precipitation_mm"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            raw_path = self.raw_dir / f"weather_pi_{start:%Y%m%d}_{end:%Y%m%d}.csv"
            frame.to_csv(raw_path, index=False, encoding="utf-8")
        return ServiceResult(
            data=frame,
            issues=issues,
            metadata={
                "source": source_detail,
                "endpoint": endpoint,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
            },
        )
