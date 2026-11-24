"""Integração com os arquivos públicos do Programa Queimadas/INPE."""

from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import date
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from config.settings import settings
from services.base import ServiceResult, build_http_session
from utils.helpers import date_range, normalize_text


CANONICAL_COLUMNS = [
    "id", "latitude", "longitude", "observed_at", "satellite", "municipality",
    "state", "municipality_id", "state_id", "days_without_rain", "precipitation_mm",
    "inpe_fire_risk", "biome", "frp", "source",
]


class INPEService:
    source_name = "INPE Programa Queimadas"

    def __init__(self, session=None) -> None:
        self.session = session or build_http_session()
        self.raw_dir = settings.raw_dir / "inpe"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _canonical_name(column: str) -> str:
        normalized = normalize_text(column).lower().replace(" ", "_")
        aliases = {
            "lat": "latitude",
            "lon": "longitude",
            "data_hora_gmt": "observed_at",
            "data_pas": "observed_at",
            "satelite": "satellite",
            "municipio": "municipality",
            "estado": "state",
            "municipio_id": "municipality_id",
            "estado_id": "state_id",
            "numero_dias_sem_chuva": "days_without_rain",
            "precipitacao": "precipitation_mm",
            "risco_fogo": "inpe_fire_risk",
            "pais": "country",
        }
        return aliases.get(normalized, normalized)

    @classmethod
    def parse_csv(cls, content: bytes | BinaryIO | Path | str) -> pd.DataFrame:
        source = io.BytesIO(content) if isinstance(content, bytes) else content
        frame = pd.read_csv(source, low_memory=False, skipinitialspace=True, encoding="utf-8")
        frame.columns = [cls._canonical_name(column) for column in frame.columns]

        for column in ("latitude", "longitude", "days_without_rain", "precipitation_mm", "inpe_fire_risk", "frp"):
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        for column in ("municipality_id", "state_id"):
            if column in frame:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
        if "observed_at" in frame:
            frame["observed_at"] = pd.to_datetime(frame["observed_at"], errors="coerce", utc=True).dt.tz_localize(None)

        if "state_id" in frame:
            frame = frame[frame["state_id"] == settings.state_code]
        elif "state" in frame:
            frame = frame[frame["state"].map(normalize_text).isin({"PIAUI", "PI"})]

        required = {"latitude", "longitude", "observed_at"}
        if not required.issubset(frame.columns):
            missing = ", ".join(sorted(required - set(frame.columns)))
            raise ValueError(f"CSV do INPE sem colunas obrigatórias: {missing}")
        frame = frame.dropna(subset=list(required)).copy()

        if "id" not in frame:
            satellite = frame["satellite"].astype(str) if "satellite" in frame else pd.Series("", index=frame.index)
            identity = (
                frame["latitude"].astype(str) + "|" + frame["longitude"].astype(str) + "|"
                + frame["observed_at"].astype(str) + "|" + satellite
            )
            frame["id"] = identity.map(lambda value: hashlib.sha256(value.encode()).hexdigest()[:32])
        for column in CANONICAL_COLUMNS:
            if column not in frame:
                frame[column] = cls.source_name if column == "source" else pd.NA
        frame["source"] = cls.source_name
        return frame[CANONICAL_COLUMNS].drop_duplicates(subset=["id"]).reset_index(drop=True)

    def _daily_url(self, day: date) -> str:
        return f"{settings.inpe_daily_base_url}/focos_diario_br_{day:%Y%m%d}.csv"

    def fetch_daily(self, start: date, end: date, persist_raw: bool = True) -> ServiceResult:
        frames: list[pd.DataFrame] = []
        issues: list[str] = []
        files: list[str] = []
        for day in date_range(start, end):
            url = self._daily_url(day)
            try:
                response = self.session.get(url, timeout=settings.request_timeout_seconds)
                if response.status_code == 404:
                    issues.append(f"INPE não publicou arquivo diário para {day:%d/%m/%Y}.")
                    continue
                response.raise_for_status()
                if persist_raw:
                    path = self.raw_dir / f"focos_diario_br_{day:%Y%m%d}.csv"
                    path.write_bytes(response.content)
                    files.append(str(path))
                parsed = self.parse_csv(response.content)
                parsed = parsed[parsed["observed_at"].dt.date == day]
                frames.append(parsed)
            except Exception as exc:
                issues.append(f"Falha ao obter INPE em {day:%d/%m/%Y}: {exc}")
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CANONICAL_COLUMNS)
        combined = combined.drop_duplicates(subset=["id"])
        return ServiceResult(
            data=combined,
            issues=issues,
            metadata={
                "source": self.source_name,
                "period_start": start.isoformat(),
                "period_end": end.isoformat(),
                "raw_files": files,
                "official_directory": settings.inpe_daily_base_url,
            },
        )

    def import_file(self, path: Path | str) -> ServiceResult:
        file_path = Path(path)
        try:
            if file_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(file_path) as archive:
                    csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
                    if not csv_names:
                        raise ValueError("O ZIP não contém arquivo CSV.")
                    with archive.open(csv_names[0]) as stream:
                        data = self.parse_csv(stream)
            else:
                data = self.parse_csv(file_path)
            return ServiceResult(data=data, metadata={"source": self.source_name, "file": str(file_path)})
        except Exception as exc:
            return ServiceResult(issues=[f"Não foi possível importar {file_path.name}: {exc}"])

    def annual_reference_url(self, year: int) -> str:
        return f"{settings.inpe_annual_pi_base_url}/focos_br_pi_ref_{year}.zip"
