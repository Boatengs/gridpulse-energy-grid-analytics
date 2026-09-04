"""Forecast baselines and strict out-of-time evaluation for GridPulse."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_seasonal_naive_prediction(
    df: pd.DataFrame,
    lag_hours: int = 168,
    demand_column: str = "demand_mwh",
) -> pd.DataFrame:
    """Predict each hour with demand from the same hour one week earlier."""
    out = df.copy().sort_values(["respondent", "period"]).reset_index(drop=True)
    out["seasonal_naive_pred_mwh"] = (
        out.groupby("respondent", sort=False)[demand_column].shift(lag_hours)
    )
    out["seasonal_naive_error_mwh"] = (
        out[demand_column] - out["seasonal_naive_pred_mwh"]
    )
    out["seasonal_naive_abs_error_mwh"] = out["seasonal_naive_error_mwh"].abs()
    return out


def regression_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    """Return scale-aware metrics without hiding missing predictions."""
    frame = pd.DataFrame({"actual": actual, "predicted": predicted}).dropna()
    if frame.empty:
        return {"mae": np.nan, "rmse": np.nan, "smape": np.nan}

    residual = frame["actual"] - frame["predicted"]
    mae = float(residual.abs().mean())
    rmse = float(np.sqrt(np.mean(np.square(residual))))
    denominator = frame["actual"].abs() + frame["predicted"].abs()
    valid = denominator > 0
    smape = (
        float((200 * residual[valid].abs() / denominator[valid]).mean())
        if valid.any()
        else np.nan
    )
    return {"mae": mae, "rmse": rmse, "smape": smape}


def evaluate_seasonal_naive(
    df: pd.DataFrame,
    test_start: str | pd.Timestamp,
    lag_hours: int = 168,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Evaluate a same-hour-last-week baseline only on rows at/after test_start."""
    work = add_seasonal_naive_prediction(df, lag_hours=lag_hours)
    cutoff = pd.Timestamp(test_start)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    else:
        cutoff = cutoff.tz_convert("UTC")

    holdout = work[work["period"] >= cutoff].copy()
    metrics = regression_metrics(
        holdout["demand_mwh"],
        holdout["seasonal_naive_pred_mwh"],
    )
    metrics["rows"] = int(holdout["seasonal_naive_pred_mwh"].notna().sum())
    return holdout, metrics


def peak_hour_metrics(
    holdout: pd.DataFrame,
    quantile: float = 0.90,
) -> dict[str, float]:
    """Measure baseline error specifically during the highest-demand holdout hours."""
    if holdout.empty or "seasonal_naive_pred_mwh" not in holdout:
        return {"threshold_mwh": np.nan, "mae": np.nan, "rows": 0}

    valid = holdout.dropna(subset=["demand_mwh", "seasonal_naive_pred_mwh"]).copy()
    if valid.empty:
        return {"threshold_mwh": np.nan, "mae": np.nan, "rows": 0}

    threshold = float(valid["demand_mwh"].quantile(quantile))
    peak = valid[valid["demand_mwh"] >= threshold]
    return {
        "threshold_mwh": threshold,
        "mae": float(
            (peak["demand_mwh"] - peak["seasonal_naive_pred_mwh"]).abs().mean()
        ),
        "rows": int(len(peak)),
    }
