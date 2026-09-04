import pandas as pd

from gridpulse.forecasting import evaluate_seasonal_naive, peak_hour_metrics


def test_seasonal_naive_same_hour_last_week():
    periods = pd.date_range("2025-01-01", periods=24 * 21, freq="h", tz="UTC")
    profile = [1000 + (i % 168) for i in range(len(periods))]
    df = pd.DataFrame(
        {
            "period": periods,
            "respondent": "PJM",
            "demand_mwh": profile,
        }
    )

    holdout, metrics = evaluate_seasonal_naive(df, "2025-01-15")
    peaks = peak_hour_metrics(holdout)

    assert metrics["mae"] == 0
    assert metrics["rmse"] == 0
    assert metrics["smape"] == 0
    assert peaks["mae"] == 0
