"""Infraestrutura HTTP compartilhada pelas integrações."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import settings


@dataclass(slots=True)
class ServiceResult:
    data: pd.DataFrame = field(default_factory=pd.DataFrame)
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return not self.data.empty


def build_http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": settings.user_agent, "Accept": "application/json,text/csv,*/*"})
    return session
