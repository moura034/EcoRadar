from pathlib import Path

import pandas as pd

from database.db import EcoRadarDatabase


def test_database_upserts_are_idempotent(tmp_path: Path):
    database = EcoRadarDatabase(tmp_path / "test.db")
    municipalities = pd.DataFrame(
        [{
            "ibge_code": 2211001,
            "name": "Teresina",
            "state_code": 22,
            "state_abbr": "PI",
            "latitude": -5.09,
            "longitude": -42.80,
            "geometry": {"type": "Polygon", "coordinates": []},
        }]
    )
    database.upsert_municipalities(municipalities)
    database.upsert_municipalities(municipalities)
    assert len(database.municipalities()) == 1

    fires = pd.DataFrame(
        [{
            "id": "abc",
            "latitude": -5.09,
            "longitude": -42.80,
            "observed_at": pd.Timestamp("2026-11-16 10:00:00"),
            "satellite": "AQUA_M-T",
            "municipality": "TERESINA",
            "municipality_id": 2211001,
            "state": "PIAUÍ",
            "state_id": 22,
            "source": "INPE Programa Queimadas",
        }]
    )
    database.upsert_fire_spots(fires)
    database.upsert_fire_spots(fires)
    assert len(database.fire_spots("2026-11-16", "2026-11-16")) == 1
