import numpy as np
import pandas as pd

from gridpulse.validation import rolling_origin_evaluation, summarize_rolling_origin


def _synthetic_grid(days: int = 220) -> pd.DataFrame:
    periods = pd.date_range("2024-01-01", periods=24 * days, freq="h", tz="UTC")
    hour = periods.hour.to_numpy()
    day = np.arange(len(periods)) / 24
    demand = (
        92_000
        + 9_000 * np.sin(2 * np.pi * hour / 24)
        + 2_000 * np.sin(2 * np.pi * day / 7)
    )
    forecast = demand + 800 + 300 * np.cos(2 * np.pi * hour / 24)
    return pd.DataFrame(
        {
            "period": periods,
            "respondent": "PJM",
            "demand_mw": demand,
            "forecast_mw": forecast,
        }
    )


def test_rolling_origin_uses_future_folds_and_common_rows():
    df = _synthetic_grid()
    benchmark, folds = rolling_origin_evaluation(
        df,
        evaluation_start="2024-06-01",
        horizon_days=20,
        step_days=20,
    )

    assert len(folds) >= 3
    assert folds["fold_start"].is_monotonic_increasing
    assert (folds["fold_end"] > folds["fold_start"]).all()
    assert set(benchmark["model"]) == {
        "EIA day-ahead",
        "Same hour last week",
        "ML-corrected EIA",
    }
    assert benchmark.groupby("fold_id")["rows"].nunique().eq(1).all()
    assert benchmark.groupby("fold_id")["peak_threshold_mw"].nunique().eq(1).all()


def test_rolling_origin_summary_reports_stability_without_overclaiming():
    folds = pd.DataFrame(
        {
            "overall_improvement_pct": [4.0, 2.0, -1.0],
            "peak_improvement_pct": [3.0, -2.0, 1.0],
            "passes_eia_gate": [True, False, False],
        }
    )
    summary = summarize_rolling_origin(folds)

    assert summary["folds"] == 3
    assert summary["valid_folds"] == 3
    assert summary["folds_beating_eia"] == 1
    assert summary["pass_rate_pct"] == 100 / 3
    assert summary["all_valid_folds_beat_eia"] is False
    assert summary["worst_overall_improvement_pct"] == -1.0
    assert summary["worst_peak_improvement_pct"] == -2.0
