"""Small, auditable EIA API v2 client for GridPulse."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import requests

BASE_URL = "https://api.eia.gov/v2/electricity/rto"
REGION_TYPES = {"D": "demand_mwh", "DF": "forecast_mwh", "NG": "net_generation_mwh", "TI": "total_interchange_mwh"}


@dataclass(frozen=True)
class EIAClient:
    api_key: str
    timeout: int = 45

    def _get(self, route: str, params: list[tuple[str, str]]) -> dict:
        # Keep the API key out of source control; callers pass it from the environment.
        query = [("api_key", self.api_key), *params]
        response = requests.get(f"{BASE_URL}/{route}/data/", params=query, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if "response" not in payload or "data" not in payload["response"]:
            raise ValueError(f"Unexpected EIA response for {route}: {payload}")
        return payload

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
            ("offset", "0"),
            ("length", "5000"),
        ]
        for type_code in types:
            params.append(("facets[type][]", type_code))
        payload = self._get("region-data", params)
        rows = pd.DataFrame(payload["response"]["data"])
        if rows.empty:
            return rows

        rows["period"] = pd.to_datetime(rows["period"], utc=True, errors="coerce")
        rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
        rows = rows[rows["type"].isin(REGION_TYPES)].copy()
        wide = (
            rows.pivot_table(index=["period", "respondent", "respondent-name"], columns="type", values="value", aggfunc="first")
            .reset_index()
            .rename(columns=REGION_TYPES)
        )
        wide.columns.name = None
        return wide.sort_values("period").reset_index(drop=True)

    def fuel_type_data(self, respondent: str, start: str, end: str, frequency: str = "hourly") -> pd.DataFrame:
        params: list[tuple[str, str]] = [
            ("frequency", frequency),
            ("data[0]", "value"),
            ("facets[respondent][]", respondent),
            ("start", start),
            ("end", end),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "asc"),
            ("offset", "0"),
            ("length", "5000"),
        ]
        payload = self._get("fuel-type-data", params)
        rows = pd.DataFrame(payload["response"]["data"])
        if rows.empty:
            return rows
        rows["period"] = pd.to_datetime(rows["period"], utc=True, errors="coerce")
        rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
        return rows.sort_values("period").reset_index(drop=True)
