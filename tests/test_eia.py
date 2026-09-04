from __future__ import annotations

from dataclasses import replace

import pandas as pd

from gridpulse.eia import EIAClient


def test_get_all_pages_until_total(monkeypatch):
    calls: list[int] = []

    def fake_get(self, route, params):
        offset = int(dict(params)["offset"])
        calls.append(offset)
        data = (
            [
                {"period": "2025-01-01T00", "respondent": "PJM", "respondent-name": "PJM", "type": "D", "value": "100"},
                {"period": "2025-01-01T00", "respondent": "PJM", "respondent-name": "PJM", "type": "DF", "value": "95"},
            ]
            if offset == 0
            else [
                {"period": "2025-01-01T01", "respondent": "PJM", "respondent-name": "PJM", "type": "D", "value": "110"},
                {"period": "2025-01-01T01", "respondent": "PJM", "respondent-name": "PJM", "type": "DF", "value": "108"},
            ]
        )
        return {"response": {"total": "4", "data": data}}

    monkeypatch.setattr(EIAClient, "_get", fake_get)
    client = replace(EIAClient("test"), page_size=2)
    result = client.region_data("PJM", "2025-01-01T00", "2025-01-01T01", types=("D", "DF"))

    assert calls == [0, 2]
    assert result["demand_mw"].tolist() == [100, 110]
    assert result["forecast_mw"].tolist() == [95, 108]
    assert pd.api.types.is_datetime64_any_dtype(result["period"])


def test_region_data_rejects_unknown_type():
    client = EIAClient("test")
    try:
        client.region_data("PJM", "2025-01-01T00", "2025-01-01T01", types=("BAD",))
    except ValueError as exc:
        assert "Unsupported EIA region-data type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown EIA type")
