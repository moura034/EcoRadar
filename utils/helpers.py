"""Funções pequenas e determinísticas usadas por várias camadas."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, TypeVar

import numpy as np
import pandas as pd

T = TypeVar("T")


def normalize_text(value: Any) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    return "".join(char for char in text if not unicodedata.combining(char)).strip().upper()


def slugify(value: str) -> str:
    text = normalize_text(value).lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def date_range(start: date, end: date) -> Iterator[date]:
    if end < start:
        raise ValueError("A data final deve ser igual ou posterior à data inicial.")
    for timestamp in pd.date_range(start, end, freq="D"):
        yield timestamp.date()


def chunked(values: Iterable[T], size: int) -> Iterator[list[T]]:
    batch: list[T] = []
    for value in values:
        batch.append(value)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def utc_now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if np.isfinite(result) else None


def dataframe_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.replace({np.nan: None, pd.NaT: None})
    return clean.to_dict(orient="records")
