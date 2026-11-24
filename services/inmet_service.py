"""Importação de dados históricos oficiais de estações do INMET.

O portal do INMET publica um ZIP por ano. Como esses arquivos são grandes e os
dados são horários por estação (não por município), a importação é batch e não é
executada a cada abertura do dashboard.
"""

from __future__ import annotations

import argparse
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from config.settings import settings
from services.base import ServiceResult, build_http_session
from utils.helpers import normalize_text


class INMETService:
    source_name = "INMET — Dados Históricos de Estações Automáticas"
    annual_url = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
    stations_url = "https://apitempo.inmet.gov.br/estacoes/T"

    def __init__(self, session=None) -> None:
        self.session = session or build_http_session()
        self.raw_dir = settings.raw_dir / "inmet"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_station_catalog(self) -> ServiceResult:
        try:
            response = self.session.get(self.stations_url, timeout=settings.request_timeout_seconds)
            response.raise_for_status()
            records = response.json()
            frame = pd.DataFrame(records)
            frame = frame[frame["SG_ESTADO"] == settings.state_abbreviation].copy()
            frame = frame.rename(
                columns={
                    "CD_ESTACAO": "station_code",
                    "DC_NOME": "station_name",
                    "CD_SITUACAO": "station_status",
                    "VL_LATITUDE": "latitude",
                    "VL_LONGITUDE": "longitude",
                    "VL_ALTITUDE": "altitude_m",
                }
            )
            for column in ("latitude", "longitude", "altitude_m"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            return ServiceResult(
                data=frame,
                metadata={"source": self.source_name, "url": self.stations_url},
            )
        except Exception as exc:
            return ServiceResult(issues=[f"Catálogo de estações INMET indisponível: {exc}"])

    def download_year(self, year: int, force: bool = False) -> Path:
        if year < 2000:
            raise ValueError("O portal de dados automáticos anuais do INMET começa em 2000.")
        target = self.raw_dir / f"{year}.zip"
        if target.exists() and not force:
            return target
        url = self.annual_url.format(year=year)
        response = self.session.get(url, timeout=max(settings.request_timeout_seconds, 180), stream=True)
        response.raise_for_status()
        temporary = target.with_suffix(".zip.part")
        with temporary.open("wb") as output:
            for block in response.iter_content(1024 * 1024):
                if block:
                    output.write(block)
        temporary.replace(target)
        return target

    @staticmethod
    def _metadata_and_frame(content: bytes) -> tuple[dict[str, Any], pd.DataFrame]:
        text = content.decode("latin-1", errors="replace")
        lines = text.splitlines()
        header_index = next(
            (index for index, line in enumerate(lines) if normalize_text(line).startswith("DATA;")),
            None,
        )
        if header_index is None:
            raise ValueError("Cabeçalho horário do INMET não encontrado.")
        metadata: dict[str, str] = {}
        for line in lines[:header_index]:
            parts = line.split(";", 1)
            if len(parts) == 2:
                metadata[normalize_text(parts[0]).rstrip(":")] = parts[1].strip().rstrip(";")
        frame = pd.read_csv(
            io.StringIO("\n".join(lines[header_index:])),
            sep=";",
            decimal=",",
            na_values=["-9999", "9999", "null", "NULL", ""],
            low_memory=False,
        )
        frame = frame.loc[:, ~frame.columns.astype(str).str.startswith("Unnamed")]
        frame.columns = [normalize_text(column) for column in frame.columns]
        return metadata, frame

    @staticmethod
    def _pick(columns: list[str], starts_with: str) -> str | None:
        normalized = normalize_text(starts_with)
        return next((column for column in columns if column.startswith(normalized)), None)

    def parse_year_zip(self, path: Path | str) -> ServiceResult:
        records: list[pd.DataFrame] = []
        issues: list[str] = []
        with zipfile.ZipFile(path) as archive:
            candidates = [
                name for name in archive.namelist()
                if name.lower().endswith(".csv") and ("_PI_" in name.upper() or " PIAUI " in normalize_text(name))
            ]
            for name in candidates:
                try:
                    metadata, frame = self._metadata_and_frame(archive.read(name))
                    columns = frame.columns.tolist()
                    date_column = self._pick(columns, "DATA")
                    temperature = self._pick(columns, "TEMPERATURA DO AR - BULBO SECO")
                    humidity = self._pick(columns, "UMIDADE RELATIVA DO AR, HORARIA")
                    wind = self._pick(columns, "VENTO, VELOCIDADE HORARIA")
                    precipitation = self._pick(columns, "PRECIPITACAO TOTAL")
                    if not date_column:
                        raise ValueError("coluna DATA ausente")
                    hourly = pd.DataFrame(
                        {
                            "observed_date": pd.to_datetime(frame[date_column], errors="coerce", dayfirst=True),
                            "temperature_c": pd.to_numeric(frame[temperature], errors="coerce") if temperature else pd.NA,
                            "humidity_pct": pd.to_numeric(frame[humidity], errors="coerce") if humidity else pd.NA,
                            "wind_speed_ms": pd.to_numeric(frame[wind], errors="coerce") if wind else pd.NA,
                            "precipitation_mm": pd.to_numeric(frame[precipitation], errors="coerce") if precipitation else pd.NA,
                        }
                    ).dropna(subset=["observed_date"])
                    daily = hourly.groupby(hourly["observed_date"].dt.date, as_index=False).agg(
                        temperature_c=("temperature_c", "mean"),
                        humidity_pct=("humidity_pct", "mean"),
                        wind_speed_ms=("wind_speed_ms", "mean"),
                        precipitation_mm=("precipitation_mm", "sum"),
                    )
                    daily = daily.rename(columns={"observed_date": "date_group"})
                    daily["observed_date"] = pd.to_datetime(daily["date_group"])
                    daily = daily.drop(columns=["date_group"])
                    daily["wind_speed_kmh"] = daily["wind_speed_ms"] * 3.6
                    daily["station_code"] = metadata.get("CODIGO (WMO)", metadata.get("CODIGO WMO", ""))
                    daily["station_name"] = metadata.get("ESTACAO", Path(name).stem)
                    daily["latitude"] = pd.to_numeric(metadata.get("LATITUDE"), errors="coerce")
                    daily["longitude"] = pd.to_numeric(metadata.get("LONGITUDE"), errors="coerce")
                    daily["source"] = self.source_name
                    records.append(daily)
                except Exception as exc:
                    issues.append(f"{name}: {exc}")
        combined = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
        if not combined.empty:
            output = self.raw_dir / (Path(path).stem + "_pi_daily.parquet")
            combined.to_parquet(output, index=False)
        return ServiceResult(
            data=combined,
            issues=issues,
            metadata={
                "source": self.source_name,
                "official_page": "https://portal.inmet.gov.br/dadoshistoricos",
                "archive": str(path),
                "station_files": len(records),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Baixa e agrega estações automáticas do INMET no Piauí.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    service = INMETService()
    archive = service.download_year(args.year, force=args.force)
    result = service.parse_year_zip(archive)
    print(json.dumps({"rows": len(result.data), "issues": result.issues, **result.metadata}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
