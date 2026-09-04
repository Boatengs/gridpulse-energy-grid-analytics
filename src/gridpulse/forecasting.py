"""Forecast baselines and strict out-of-time evaluation for GridPulse."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_seasonal_naive_prediction(
    df: pd.DataFrame,
    lag_hours: int = 168,
    demand_column: str = "demand_mw",
) -> pd.DataFrame:
    """Predict each hour with the same respondent's demand exactly one week earlier."""
    out = df.copy()
    out["period"] = pd.to_datetime(out["period"], utc=True)
    out = out.sort_values(["respondent", "period"]).reset_index(drop=True)

    history = out[["respondent", "period", demand_column]].copy()
    history["period"] = history["period"] + pd.Timedelta(hours=lag_hours)
    history = history.rename(columns={demand_column: "seasonal_naive_pred_mw"})

    out = out.merge(history, on=["respondent", "period"], how="left", validate="one_to_one")
    out["seasonal_naive_error_mw"] = out[demand_column] - out["seasonal_naive_pred_mw"]
    out["seasonal_naive_abs_error_mw"] = out["seasonal_naive_error_mw"].abs()
    return out


def regression_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """Return MAE, RMSE and sMAPE on rows where both values exist."""
    frame = pd.DataFrame({"actual": actual, "predicted": predicted}).dropna()
    if frame.empty:
        return {"mae": np.nan, "rmse": np.nan, "smape": np.nan, "rows": 0}

    residual = frame["actual"] - frame["predicted"]
    denominator = frame["actual"].abs() + frame["predicted"].abs()
    valid = denominator > 0
    return {
        "mae": float(residual.abs().mean()),
        "rmse": float(np.sqrt(np.mean(np.square(residual)))),
        "smape": (
            float((200 * residual[valid].abs() / denominator[valid]).mean())
            if valid.any()
            else np.nan
        ),
        "rows": int(len(frame)),
    }


def _utc_cutoff(test_start: str | pd.Timestamp) -> pd.Timestamp:
    cutoff = pd.Timestamp(test_start)
    return cutoff.tz_localize("UTC") if cutoff.tzinfo is None else cutoff.tz_convert("UTC")


def evaluate_seasonal_naive(
    df: pd.DataFrame,
    test_start: str | pd.Timestamp,
    lag_hours: int = 168,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Evaluate a same-hour-last-week baseline only on rows at/after test_start."""
    work = add_seasonal_naive_prediction(df, lag_hours=lag_hours)
    holdout = work[work["period"] >= _utc_cutoff(test_start)].copy()
    metrics = regression_metrics(holdout["demand_mw"], holdout["seasonal_naive_pred_mw"])
    return holdout, metrics


def evaluate_reported_forecast(
    df: pd.DataFrame,
    test_start: str | pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Evaluate EIA's reported day-ahead demand forecast on the same holdout."""
    work = df.copy()
    work["period"] = pd.to_datetime(work["period"], utc=True)
    holdout = work[work["period"] >= _utc_cutoff(test_start)].copy()
    metrics = regression_metrics(holdout["demand_mw"], holdout["forecast_mw"])
    return holdout, metrics


def peak_hour_metrics(
    holdout: pd.DataFrame,
    predicted_column: str = "seasonal_naive_pred_mw",
    quantile: float = 0.90,
) -> dict[str, float]:
    """Measure forecast error specifically during highest-demand holdout hours."""
    if holdout.empty or predicted_column not in holdout:
        return {"threshold_mw": np.nan, "mae": np.nan, "rows": 0}

    valid = holdout.dropna(subset=["demand_mw", predicted_column]).copy()
    if valid.empty:
        return {"threshold_mw": np.nan, "mae": np.nan, "rows": 0}

    threshold = float(valid["demand_mw"].quantile(quantile))
    peak = valid[valid["demand_mw"] >= threshold]
    return {
        "threshold_mw": threshold,
        "mae": float((peak["demand_mw"] - peak[predicted_column]).abs().mean()),
        "rows": int(len(peak)),
    }
