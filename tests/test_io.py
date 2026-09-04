from pathlib import Path

import pandas as pd

from gridpulse.io import hourly_qa_summary, load_fuel_exports, load_region_exports


def test_load_region_exports_from_eia_long_form(tmp_path: Path):
    rows = pd.DataFrame(
        {
            "period": ["2025-01-01T00", "2025-01-01T00", "2025-01-01T00", "2025-01-01T00"],
            "respondent": ["PJM"] * 4,
            "respondent-name": ["PJM Interconnection"] * 4,
            "type": ["D", "DF", "NG", "TI"],
            "value": [1000, 980, 995, -15],
        }
    )
    path = tmp_path / "region.csv"
    rows.to_csv(path, index=False)

    out = load_region_exports(path)

    assert len(out) == 1
    assert out.loc[0, "demand_mwh"] == 1000
    assert out.loc[0, "forecast_mwh"] == 980
    assert out.loc[0, "net_generation_mwh"] == 995
    assert out.loc[0, "total_interchange_mwh"] == -15


def test_load_fuel_exports(tmp_path: Path):
    rows = pd.DataFrame(
        {
            "period": ["2025-01-01T00", "2025-01-01T00"],
            "respondent": ["PJM", "PJM"],
            "respondent-name": ["PJM Interconnection", "PJM Interconnection"],
            "fueltype": ["Natural Gas", "Wind"],
            "value": [600, 150],
        }
    )
    path = tmp_path / "fuel.csv"
    rows.to_csv(path, index=False)

    out = load_fuel_exports(path)

    assert set(out["fuel_type"]) == {"Natural Gas", "Wind"}
    assert out["generation_mwh"].sum() == 750


def test_hourly_qa_summary_detects_gap():
    df = pd.DataFrame(
        {
            "period": pd.to_datetime(
                ["2025-01-01T00Z", "2025-01-01T02Z"],
                utc=True,
            ),
            "respondent": ["PJM", "PJM"],
            "demand_mwh": [1000, 1100],
        }
    )

    qa = hourly_qa_summary(df)
    assert qa["missing_hour_slots"] == 1
