from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from gridpulse.slicing import forecast_error_slices, summarize_error_slices


def prediction_frame(hours: int = 24 * 20) -> pd.DataFrame:
    period = pd.date_range("2025-01-01", periods=hours, freq="h", tz="UTC")
    local = period.tz_convert("America/New_York").tz_localize(None)
    base = 90_000 + 10_000 * np.sin(np.arange(hours) * 2 * np.pi / 24)
    eia_error = 3_000 + 500 * np.sin(np.arange(hours) * 2 * np.pi / 168)
    ml_error = eia_error * 0.5
    return pd.DataFrame(
        {
            "period": period,
            "local_time": local,
            "demand_mw": base,
            "forecast_mw": base - eia_error,
            "ml_eia_corrected_pred_mw": base - ml_error,
        }
    )


def test_error_slices_use_common_rows_and_expected_dimensions() -> None:
    frame = prediction_frame()
    frame.loc[3, "forecast_mw"] = np.nan
    frame.loc[4, "ml_eia_corrected_pred_mw"] = np.nan
    tables = forecast_error_slices(frame)

    assert set(tables) == {"hour", "month", "season", "day_type", "demand_decile"}
    assert int(tables["hour"]["rows"].sum()) == len(frame) - 2
    assert tables["hour"]["slice"].tolist() == list(range(24))
    assert tables["demand_decile"]["slice"].astype(str).tolist() == [f"D{i}" for i in range(1, 11)]


def test_slice_improvement_is_fifty_percent_for_scaled_errors() -> None:
    tables = forecast_error_slices(prediction_frame())
    for table in tables.values():
        assert np.allclose(table["improvement_pct"].to_numpy(), 50.0)


def test_summary_reports_highest_demand_decile() -> None:
    tables = forecast_error_slices(prediction_frame())
    summary = summarize_error_slices(tables)
    assert summary["highest_demand_decile"]["slice"] == "D10"
    assert summary["highest_demand_decile"]["improvement_pct"] == pytest.approx(50.0)


def test_invalid_decile_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        forecast_error_slices(prediction_frame(), demand_deciles=1)


def test_missing_prediction_columns_are_rejected() -> None:
    with pytest.raises(ValueError):
        forecast_error_slices(pd.DataFrame({"period": ["2025-01-01"]}))
