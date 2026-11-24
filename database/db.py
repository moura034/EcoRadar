"""Camada de acesso ao SQLite com operações idempotentes."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable, Iterator

import pandas as pd

from config.settings import settings
from utils.helpers import dataframe_records, json_dumps, utc_now_iso


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS municipalities (
    ibge_code INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    state_code INTEGER NOT NULL DEFAULT 22,
    state_abbr TEXT NOT NULL DEFAULT 'PI',
    latitude REAL,
    longitude REAL,
    geometry_json TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fire_spots (
    id TEXT PRIMARY KEY,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    observed_at TEXT NOT NULL,
    satellite TEXT,
    municipality TEXT,
    municipality_id INTEGER,
    state TEXT,
    state_id INTEGER,
    days_without_rain REAL,
    precipitation_mm REAL,
    inpe_fire_risk REAL,
    biome TEXT,
    frp REAL,
    source TEXT NOT NULL DEFAULT 'INPE Programa Queimadas',
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fire_date ON fire_spots(observed_at);
CREATE INDEX IF NOT EXISTS idx_fire_municipality ON fire_spots(municipality_id);

CREATE TABLE IF NOT EXISTS weather_daily (
    municipality_id INTEGER NOT NULL,
    municipality TEXT NOT NULL,
    observed_date TEXT NOT NULL,
    temperature_c REAL,
    humidity_pct REAL,
    wind_speed_kmh REAL,
    wind_direction_deg REAL,
    precipitation_mm REAL,
    latitude REAL,
    longitude REAL,
    source TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    PRIMARY KEY (municipality_id, observed_date, source)
);

CREATE INDEX IF NOT EXISTS idx_weather_date ON weather_daily(observed_date);

CREATE TABLE IF NOT EXISTS risk_snapshots (
    municipality_id INTEGER NOT NULL,
    municipality TEXT NOT NULL,
    observed_date TEXT NOT NULL,
    risk_score REAL,
    risk_class TEXT NOT NULL,
    risk_method TEXT NOT NULL,
    factors_json TEXT,
    source_summary TEXT,
    calculated_at TEXT NOT NULL,
    PRIMARY KEY (municipality_id, observed_date, risk_method)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    municipality_id INTEGER NOT NULL,
    municipality TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    risk_score REAL NOT NULL,
    observed_at TEXT NOT NULL,
    factors_json TEXT NOT NULL,
    source_summary TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Ativo',
    created_at TEXT NOT NULL,
    UNIQUE(municipality_id, observed_at, risk_level)
);

CREATE TABLE IF NOT EXISTS source_updates (
    source TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    records_count INTEGER NOT NULL DEFAULT 0,
    period_start TEXT,
    period_end TEXT,
    message TEXT,
    updated_at TEXT NOT NULL,
    metadata_json TEXT
);
"""


class EcoRadarDatabase:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path or settings.database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def _upsert(self, table: str, frame: pd.DataFrame, columns: list[str], conflict: list[str]) -> int:
        if frame.empty:
            return 0
        available = [column for column in columns if column in frame.columns]
        records = dataframe_records(frame[available])
        placeholders = ",".join(f":{column}" for column in available)
        updates = [column for column in available if column not in conflict]
        update_clause = ",".join(f"{column}=excluded.{column}" for column in updates)
        conflict_clause = ",".join(conflict)
        sql = (
            f"INSERT INTO {table} ({','.join(available)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_clause}) DO UPDATE SET {update_clause}"
        )
        with self.connect() as connection:
            connection.executemany(sql, records)
        return len(records)

    def upsert_municipalities(self, frame: pd.DataFrame) -> int:
        data = frame.copy()
        data["updated_at"] = utc_now_iso()
        if "geometry" in data:
            data["geometry_json"] = data["geometry"].map(json_dumps)
        return self._upsert(
            "municipalities",
            data,
            [
                "ibge_code", "name", "state_code", "state_abbr", "latitude", "longitude",
                "geometry_json", "updated_at",
            ],
            ["ibge_code"],
        )

    def upsert_fire_spots(self, frame: pd.DataFrame) -> int:
        data = frame.copy()
        data["imported_at"] = utc_now_iso()
        if "observed_at" in data:
            data["observed_at"] = pd.to_datetime(data["observed_at"]).dt.strftime("%Y-%m-%dT%H:%M:%S")
        return self._upsert(
            "fire_spots",
            data,
            [
                "id", "latitude", "longitude", "observed_at", "satellite", "municipality",
                "municipality_id", "state", "state_id", "days_without_rain", "precipitation_mm",
                "inpe_fire_risk", "biome", "frp", "source", "imported_at",
            ],
            ["id"],
        )

    def upsert_weather(self, frame: pd.DataFrame) -> int:
        data = frame.copy()
        data["imported_at"] = utc_now_iso()
        if "observed_date" in data:
            data["observed_date"] = pd.to_datetime(data["observed_date"]).dt.strftime("%Y-%m-%d")
        return self._upsert(
            "weather_daily",
            data,
            [
                "municipality_id", "municipality", "observed_date", "temperature_c",
                "humidity_pct", "wind_speed_kmh", "wind_direction_deg", "precipitation_mm",
                "latitude", "longitude", "source", "imported_at",
            ],
            ["municipality_id", "observed_date", "source"],
        )

    def upsert_risk_snapshots(self, frame: pd.DataFrame) -> int:
        data = frame.copy()
        data["calculated_at"] = utc_now_iso()
        if "observed_date" in data:
            data["observed_date"] = pd.to_datetime(data["observed_date"]).dt.strftime("%Y-%m-%d")
        if "factors" in data:
            data["factors_json"] = data["factors"].map(json_dumps)
        return self._upsert(
            "risk_snapshots",
            data,
            [
                "municipality_id", "municipality", "observed_date", "risk_score", "risk_class",
                "risk_method", "factors_json", "source_summary", "calculated_at",
            ],
            ["municipality_id", "observed_date", "risk_method"],
        )

    def create_alerts(self, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0
        records = []
        now = utc_now_iso()
        for record in dataframe_records(frame):
            records.append(
                {
                    "municipality_id": record["municipality_id"],
                    "municipality": record["municipality"],
                    "risk_level": record["risk_class"],
                    "risk_score": record["risk_score"],
                    "observed_at": str(record["observed_date"]),
                    "factors_json": json_dumps(record.get("factors", [])),
                    "source_summary": record.get("source_summary", ""),
                    "created_at": now,
                }
            )
        sql = """
            INSERT INTO alerts (
                municipality_id, municipality, risk_level, risk_score, observed_at,
                factors_json, source_summary, created_at
            ) VALUES (
                :municipality_id, :municipality, :risk_level, :risk_score, :observed_at,
                :factors_json, :source_summary, :created_at
            ) ON CONFLICT (municipality_id, observed_at, risk_level) DO UPDATE SET
                risk_score=excluded.risk_score,
                factors_json=excluded.factors_json,
                source_summary=excluded.source_summary,
                created_at=excluded.created_at
        """
        with self.connect() as connection:
            before = connection.total_changes
            connection.executemany(sql, records)
            return connection.total_changes - before

    def record_source_update(
        self,
        source: str,
        status: str,
        records_count: int = 0,
        period_start: str | None = None,
        period_end: str | None = None,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        sql = """
            INSERT INTO source_updates (
                source, status, records_count, period_start, period_end, message, updated_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                status=excluded.status, records_count=excluded.records_count,
                period_start=excluded.period_start, period_end=excluded.period_end,
                message=excluded.message, updated_at=excluded.updated_at,
                metadata_json=excluded.metadata_json
        """
        with self.connect() as connection:
            connection.execute(
                sql,
                (
                    source, status, records_count, period_start, period_end, message,
                    utc_now_iso(), json_dumps(metadata or {}),
                ),
            )

    def read_frame(self, query: str, params: Iterable[Any] = ()) -> pd.DataFrame:
        with self.connect() as connection:
            return pd.read_sql_query(query, connection, params=tuple(params))

    def municipalities(self) -> pd.DataFrame:
        return self.read_frame("SELECT * FROM municipalities ORDER BY name")

    def fire_spots(self, start: str, end: str) -> pd.DataFrame:
        return self.read_frame(
            """SELECT * FROM fire_spots
               WHERE date(observed_at) BETWEEN date(?) AND date(?)
               ORDER BY observed_at""",
            (start, end),
        )

    def weather(self, start: str, end: str) -> pd.DataFrame:
        return self.read_frame(
            """SELECT * FROM weather_daily
               WHERE date(observed_date) BETWEEN date(?) AND date(?)
               ORDER BY observed_date, municipality""",
            (start, end),
        )

    def latest_risk(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        filters = ""
        params: tuple[Any, ...] = ()
        if start and end:
            filters = "WHERE date(observed_date) BETWEEN date(?) AND date(?)"
            params = (start, end)
        return self.read_frame(
            f"""
            SELECT r.* FROM risk_snapshots r
            JOIN (
                SELECT municipality_id, MAX(observed_date) AS latest_date
                FROM risk_snapshots {filters} GROUP BY municipality_id
            ) latest
              ON latest.municipality_id = r.municipality_id
             AND latest.latest_date = r.observed_date
            ORDER BY r.risk_score DESC
            """,
            params,
        )

    def alerts(self, start: str | None = None, end: str | None = None) -> pd.DataFrame:
        if start and end:
            return self.read_frame(
                """SELECT * FROM alerts WHERE date(observed_at) BETWEEN date(?) AND date(?)
                   ORDER BY observed_at DESC, risk_score DESC""",
                (start, end),
            )
        return self.read_frame("SELECT * FROM alerts ORDER BY observed_at DESC, risk_score DESC")

    def source_updates(self) -> pd.DataFrame:
        return self.read_frame("SELECT * FROM source_updates ORDER BY updated_at DESC")
