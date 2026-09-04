import pandas as pd
from gridpulse.forecasting import evaluate_seasonal_naive


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
