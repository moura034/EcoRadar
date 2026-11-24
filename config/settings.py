"""Configuração central, sem segredos no código-fonte."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = "EcoRadar"
    slogan: str = "Inteligência que antecipa riscos."
    state_code: int = 22
    state_abbreviation: str = "PI"
    timezone: str = "America/Fortaleza"
    request_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("ECORADAR_HTTP_TIMEOUT", "60"))
    )
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("ECORADAR_CACHE_TTL", "3600"))
    )
    max_live_days: int = field(
        default_factory=lambda: int(os.getenv("ECORADAR_MAX_LIVE_DAYS", "31"))
    )
    user_agent: str = "EcoRadar-academic/1.0 (Big Data research project)"

    @property
    def data_dir(self) -> Path:
        return BASE_DIR / "data"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def model_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def database_path(self) -> Path:
        configured = os.getenv("ECORADAR_DATABASE_PATH")
        return Path(configured).expanduser().resolve() if configured else self.data_dir / "ecoradar.db"

    @property
    def inpe_daily_base_url(self) -> str:
        return (
            "https://dataserver-coids.inpe.br/queimadas/queimadas/"
            "focos/csv/diario/Brasil"
        )

    @property
    def inpe_annual_pi_base_url(self) -> str:
        return (
            "https://dataserver-coids.inpe.br/queimadas/queimadas/"
            "focos/csv/anual/EstadosBr_sat_ref/PI"
        )

    @property
    def ibge_municipalities_url(self) -> str:
        return (
            "https://servicodados.ibge.gov.br/api/v1/localidades/"
            f"estados/{self.state_code}/municipios?orderBy=nome"
        )

    @property
    def ibge_mesh_url(self) -> str:
        return (
            "https://servicodados.ibge.gov.br/api/v3/malhas/"
            f"estados/{self.state_code}"
            "?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio"
        )

    open_meteo_forecast_url: str = "https://api.open-meteo.com/v1/forecast"
    open_meteo_archive_url: str = "https://archive-api.open-meteo.com/v1/archive"

    def ensure_directories(self) -> None:
        for path in (self.raw_dir, self.processed_dir, self.model_dir, self.database_path.parent):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
