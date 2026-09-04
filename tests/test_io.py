from pathlib import Path

import pandas as pd

from gridpulse.io import hourly_qa_summary, load_fuel_exports, load_region_exports


def test_load_region_exports_from_eia_long_form(tmp_path: Path):
    rows = pd.DataFrame(
        {
            "period": ["2025-01-01T00"] * 4,
            "respondent": ["PJM"] * 4,
            "type": ["D", "DF", "NG", "TI"],
            "value": [1000, 980, 995, -5],
        }
    )
    path = tmp_path / "region.csv"
    rows.to_csv(path, index=False)
    out = load_region_exports(path)
    assert out.loc[0, "demand_mw"] == 1000
    assert out.loc[0, "forecast_mw"] == 980
    assert out.loc[0, "net_generation_mw"] == 995
    assert out.loc[0, "total_interchange_mw"] == -5


def test_load_fuel_exports(tmp_path: Path):
    rows = pd.DataFrame(
        {
            "period": ["2025-01-01T00", "2025-01-01T00"],
            "respondent": ["PJM", "PJM"],
            "fueltype": ["Natural Gas", "Wind"],
            "value": [600, 150],
        }
    )
    path = tmp_path / "fuel.csv"
    rows.to_csv(path, index=False)
    out = load_fuel_exports(path)
    assert set(out["fuel_type"]) == {"Natural Gas", "Wind"}
    assert out["generation_mw"].sum() == 750


def test_hourly_qa_summary_detects_gap_and_missing_fields():
    df = pd.DataFrame(
        {
            "period": pd.to_datetime(["2025-01-01T00Z", "2025-01-01T02Z"], utc=True),
            "respondent": ["PJM", "PJM"],
            "demand_mw": [1000, 1100],
            "forecast_mw": [990, None],
            "net_generation_mw": [1005, 1105],
            "total_interchange_mw": [5, 5],
        }
    )
    qa = hourly_qa_summary(df)
    assert qa["missing_hour_slots"] == 1
    assert qa["missing_forecast"] == 1
