"""Small, auditable EIA API v2 client for GridPulse."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests

BASE_URL = "https://api.eia.gov/v2/electricity/rto"
REGION_TYPES = {
    "D": "demand_mw",
    "DF": "forecast_mw",
    "NG": "net_generation_mw",
    "TI": "total_interchange_mw",
}


@dataclass(frozen=True)
class EIAClient:
    api_key: str
    timeout: int = 45
    page_size: int = 5000

    def _get(self, route: str, params: list[tuple[str, str]]) -> dict:
        query = [("api_key", self.api_key), *params]
        response = requests.get(f"{BASE_URL}/{route}/data/", params=query, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if "response" not in payload or "data" not in payload["response"]:
            raise ValueError(f"Unexpected EIA response for {route}: {payload}")
        return payload

    def _get_all(self, route: str, params: list[tuple[str, str]]) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        offset = 0
        total: int | None = None
        while total is None or offset < total:
            payload = self._get(
                route,
                [*params, ("offset", str(offset)), ("length", str(self.page_size))],
            )
            response = payload["response"]
            page = pd.DataFrame(response["data"])
            if page.empty:
                break
            frames.append(page)
            total = int(response.get("total", len(page)))
            offset += len(page)
            if len(page) < self.page_size:
                break
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def region_data(
        self,
        respondent: str,
        start: str,
        end: str,
        types: Iterable[str] = ("D", "DF", "NG", "TI"),
        frequency: str = "hourly",
    ) -> pd.DataFrame:
        params: list[tuple[str, str]] = [
            ("frequency", frequency),
            ("data[0]", "value"),
            ("facets[respondent][]", respondent),
            ("start", start),
            ("end", end),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
        ]
        for type_code in types:
            if type_code not in REGION_TYPES:
                raise ValueError(f"Unsupported EIA region-data type: {type_code}")
            params.append(("facets[type][]", type_code))

        rows = self._get_all("region-data", params)
        if rows.empty:
            return rows
        rows["period"] = pd.to_datetime(rows["period"], utc=True, errors="coerce")
        rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
        rows = rows[rows["type"].isin(REGION_TYPES)].copy()
        wide = (
            rows.pivot_table(
                index=["period", "respondent", "respondent-name"],
                columns="type",
                values="value",
                aggfunc="first",
            )
            .reset_index()
            .rename(columns=REGION_TYPES)
        )
        wide.columns.name = None
        return wide.sort_values("period").reset_index(drop=True)

    def fuel_type_data(
        self,
        respondent: str,
        start: str,
        end: str,
        frequency: str = "hourly",
    ) -> pd.DataFrame:
        params: list[tuple[str, str]] = [
            ("frequency", frequency),
            ("data[0]", "value"),
            ("facets[respondent][]", respondent),
            ("start", start),
            ("end", end),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
        ]
        rows = self._get_all("fuel-type-data", params)
        if rows.empty:
            return rows
        rows["period"] = pd.to_datetime(rows["period"], utc=True, errors="coerce")
        rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
        return rows.sort_values("period").reset_index(drop=True)
