import numpy as np
import pandas as pd

from gridpulse.forecasting import (
    add_day_ahead_model_features,
    benchmark_forecasts,
    evaluate_seasonal_naive,
    promotion_gate,
)


def test_seasonal_naive_uses_exact_time_lag():
    periods = pd.date_range("2025-01-01", periods=24 * 15, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "period": periods,
            "respondent": "PJM",
            "demand_mw": list(range(len(periods))),
        }
    )
    holdout, metrics = evaluate_seasonal_naive(df, "2025-01-08")
    valid = holdout.dropna(subset=["seasonal_naive_pred_mw"])
    assert (valid["demand_mw"] - valid["seasonal_naive_pred_mw"]).eq(168).all()
    assert metrics["mae"] == 168


def test_day_ahead_features_use_exact_lags_at_least_48_hours():
    periods = pd.date_range("2024-01-01", periods=24 * 20, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "period": periods,
            "respondent": "PJM",
            "demand_mw": np.arange(len(periods), dtype=float),
            "forecast_mw": np.arange(len(periods), dtype=float) + 10,
        }
    )
    out = add_day_ahead_model_features(df)
    row = out.iloc[400]
    assert row["demand_lag_48h_mw"] == 352
    assert row["demand_lag_168h_mw"] == 232
    assert "demand_lag_24h_mw" not in out


def test_benchmark_uses_identical_rows_and_shared_peak_threshold():
    holdout = pd.DataFrame(
        {
            "demand_mw": [100, 200, 300, 400, 500],
            "forecast_mw": [110, 190, 290, 390, 510],
            "seasonal_naive_pred_mw": [100, 200, np.nan, 380, 480],
            "ml_eia_corrected_pred_mw": [105, 205, 305, 405, 505],
        }
    )
    table = benchmark_forecasts(holdout, peak_quantile=0.75)
    assert table["rows"].nunique() == 1
    assert table["rows"].iloc[0] == 4
    assert table["peak_threshold_mw"].nunique() == 1


def test_promotion_gate_requires_beating_eia_overall_and_at_peak():
    table = pd.DataFrame(
        {
            "model": ["EIA day-ahead", "ML-corrected EIA"],
            "mae_mw": [100.0, 90.0],
            "peak_mae_mw": [150.0, 160.0],
        }
    )
    gate = promotion_gate(table)
    assert gate["passes"] is False
    table.loc[table["model"].eq("ML-corrected EIA"), "peak_mae_mw"] = 140.0
    gate = promotion_gate(table)
    assert gate["passes"] is True
