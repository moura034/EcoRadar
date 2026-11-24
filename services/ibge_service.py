"""Municípios e malhas oficiais do IBGE."""

from __future__ import annotations

import json
from typing import Any, Iterable

import pandas as pd

from config.settings import settings
from services.base import ServiceResult, build_http_session


def _rings(geometry: dict[str, Any]) -> Iterable[list[list[float]]]:
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        for ring in coordinates:
            yield ring
    elif geometry.get("type") == "MultiPolygon":
        for polygon in coordinates:
            for ring in polygon:
                yield ring


def _ring_centroid(ring: list[list[float]]) -> tuple[float, float, float]:
    area_twice = 0.0
    cx = 0.0
    cy = 0.0
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][:2]
        x2, y2 = ring[index + 1][:2]
        cross = x1 * y2 - x2 * y1
        area_twice += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area_twice) < 1e-12:
        xs = [point[0] for point in ring]
        ys = [point[1] for point in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys), 0.0
    return cx / (3 * area_twice), cy / (3 * area_twice), abs(area_twice / 2)


def geometry_centroid(geometry: dict[str, Any]) -> tuple[float | None, float | None]:
    candidates = [_ring_centroid(ring) for ring in _rings(geometry) if len(ring) >= 4]
    if not candidates:
        return None, None
    longitude, latitude, _ = max(candidates, key=lambda item: item[2])
    return latitude, longitude


class IBGEService:
    source_name = "IBGE API de Localidades e Malhas"

    def __init__(self, session=None) -> None:
        self.session = session or build_http_session()
        self.raw_dir = settings.raw_dir / "ibge"
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_municipalities(self) -> ServiceResult:
        issues: list[str] = []
        try:
            municipalities_response = self.session.get(
                settings.ibge_municipalities_url,
                timeout=settings.request_timeout_seconds,
            )
            municipalities_response.raise_for_status()
            municipalities_json = municipalities_response.json()

            mesh_response = self.session.get(settings.ibge_mesh_url, timeout=settings.request_timeout_seconds)
            mesh_response.raise_for_status()
            geojson = mesh_response.json()
            (self.raw_dir / "municipios_pi.geojson").write_text(
                json.dumps(geojson, ensure_ascii=False), encoding="utf-8"
            )
            (self.raw_dir / "municipios_pi.json").write_text(
                json.dumps(municipalities_json, ensure_ascii=False), encoding="utf-8"
            )

            names = {int(item["id"]): item["nome"] for item in municipalities_json}
            records: list[dict[str, Any]] = []
            for feature in geojson.get("features", []):
                code = int(feature.get("properties", {}).get("codarea"))
                latitude, longitude = geometry_centroid(feature.get("geometry", {}))
                records.append(
                    {
                        "ibge_code": code,
                        "name": names.get(code, str(code)),
                        "state_code": settings.state_code,
                        "state_abbr": settings.state_abbreviation,
                        "latitude": latitude,
                        "longitude": longitude,
                        "geometry": feature.get("geometry"),
                    }
                )
            frame = pd.DataFrame(records).sort_values("name").reset_index(drop=True)
            if len(frame) != 224:
                issues.append(f"IBGE retornou {len(frame)} municípios; eram esperados 224 para o Piauí.")
            return ServiceResult(
                data=frame,
                issues=issues,
                metadata={
                    "source": self.source_name,
                    "municipalities_url": settings.ibge_municipalities_url,
                    "mesh_url": settings.ibge_mesh_url,
                    "geojson": geojson,
                },
            )
        except Exception as exc:
            return ServiceResult(issues=[f"IBGE indisponível: {exc}"], metadata={"source": self.source_name})

    def load_cached_geojson(self) -> dict[str, Any] | None:
        path = self.raw_dir / "municipios_pi.geojson"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
