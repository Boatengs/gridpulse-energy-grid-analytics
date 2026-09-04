"""Forecast baselines, model candidates, and strict out-of-time evaluation for GridPulse."""
from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor


DAY_AHEAD_MODEL_FEATURES = (
    "forecast_mw",
    "hour_sin",
    "hour_cos",
    "dow_sin",
    "dow_cos",
    "month_sin",
    "month_cos",
    "demand_lag_48h_mw",
    "demand_lag_168h_mw",
    "demand_lag_336h_mw",
    "eia_error_lag_48h_mw",
    "eia_error_lag_168h_mw",
)


def _prepare_hourly(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["period"] = pd.to_datetime(out["period"], utc=True)
    if "respondent" not in out:
        out["respondent"] = "UNKNOWN"
    return out.sort_values(["respondent", "period"]).reset_index(drop=True)


def _add_exact_lag(
    df: pd.DataFrame,
    source_column: str,
    lag_hours: int,
    output_column: str,
) -> pd.DataFrame:
    history = df[["respondent", "period", source_column]].copy()
    history["period"] = history["period"] + pd.Timedelta(hours=lag_hours)
    history = history.rename(columns={source_column: output_column})
    return df.merge(history, on=["respondent", "period"], how="left", validate="one_to_one")


def add_seasonal_naive_prediction(
    df: pd.DataFrame,
    lag_hours: int = 168,
    demand_column: str = "demand_mw",
) -> pd.DataFrame:
    """Predict each hour with the same respondent's demand exactly one week earlier."""
    out = _prepare_hourly(df)
    out = _add_exact_lag(out, demand_column, lag_hours, "seasonal_naive_pred_mw")
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
    work = _prepare_hourly(df)
    holdout = work[work["period"] >= _utc_cutoff(test_start)].copy()
    metrics = regression_metrics(holdout["demand_mw"], holdout["forecast_mw"])
    return holdout, metrics


def peak_hour_metrics(
    holdout: pd.DataFrame,
    predicted_column: str = "seasonal_naive_pred_mw",
    quantile: float = 0.90,
    threshold_mw: float | None = None,
) -> dict[str, float]:
    """Measure forecast error during highest-demand holdout hours."""
    if holdout.empty or predicted_column not in holdout:
        return {"threshold_mw": np.nan, "mae": np.nan, "rows": 0}

    valid = holdout.dropna(subset=["demand_mw", predicted_column]).copy()
    if valid.empty:
        return {"threshold_mw": np.nan, "mae": np.nan, "rows": 0}

    threshold = (
        float(valid["demand_mw"].quantile(quantile))
        if threshold_mw is None
        else float(threshold_mw)
    )
    peak = valid[valid["demand_mw"] >= threshold]
    return {
        "threshold_mw": threshold,
        "mae": float((peak["demand_mw"] - peak[predicted_column]).abs().mean()),
        "rows": int(len(peak)),
    }


def add_day_ahead_model_features(df: pd.DataFrame) -> pd.DataFrame:
    """Build conservative features for correcting EIA's day-ahead forecast.

    All observed-demand and prior-error features are exact-time lags of at least 48
    hours. That avoids giving the model same-day observations that may not have been
    available when a day-ahead forecast was issued. The reported EIA forecast for the
    target hour is intentionally included because this candidate is a forecast-correction
    model, not a replacement weather/load-forecast stack.
    """
    required = {"period", "demand_mw", "forecast_mw"}
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError("Day-ahead modeling requires: " + ", ".join(missing))

    out = _prepare_hourly(df)
    hour = out["period"].dt.hour.astype(float)
    dow = out["period"].dt.dayofweek.astype(float)
    month = out["period"].dt.month.astype(float)
    out["hour_sin"] = np.sin(2 * np.pi * hour / 24)
    out["hour_cos"] = np.cos(2 * np.pi * hour / 24)
    out["dow_sin"] = np.sin(2 * np.pi * dow / 7)
    out["dow_cos"] = np.cos(2 * np.pi * dow / 7)
    out["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
    out["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)

    for lag in (48, 168, 336):
        out = _add_exact_lag(out, "demand_mw", lag, f"demand_lag_{lag}h_mw")

    out["_eia_error_mw"] = out["demand_mw"] - out["forecast_mw"]
    for lag in (48, 168):
        out = _add_exact_lag(out, "_eia_error_mw", lag, f"eia_error_lag_{lag}h_mw")
    return out.drop(columns="_eia_error_mw")


def fit_eia_residual_candidate(
    df: pd.DataFrame,
    test_start: str | pd.Timestamp,
    min_train_rows: int = 24 * 90,
) -> tuple[pd.DataFrame, dict[str, int | str | float]]:
    """Fit a fixed gradient-boosted residual correction on pre-holdout history."""
    cutoff = _utc_cutoff(test_start)
    work = add_day_ahead_model_features(df)
    work = add_seasonal_naive_prediction(work)

    train = work[work["period"] < cutoff].dropna(
        subset=["demand_mw", *DAY_AHEAD_MODEL_FEATURES]
    )
    holdout = work[work["period"] >= cutoff].copy()
    holdout["ml_eia_corrected_pred_mw"] = np.nan

    info: dict[str, int | str | float] = {
        "train_rows": int(len(train)),
        "test_rows": int(len(holdout)),
        "test_start": cutoff.isoformat(),
        "feature_count": len(DAY_AHEAD_MODEL_FEATURES),
    }
    if len(train) < min_train_rows:
        info["status"] = "insufficient_training_history"
        return holdout, info

    model = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=200,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=42,
    )
    residual_target = train["demand_mw"] - train["forecast_mw"]
    model.fit(train[list(DAY_AHEAD_MODEL_FEATURES)], residual_target)

    valid = holdout[list(DAY_AHEAD_MODEL_FEATURES)].notna().all(axis=1)
    if valid.any():
        correction = model.predict(holdout.loc[valid, list(DAY_AHEAD_MODEL_FEATURES)])
        holdout.loc[valid, "ml_eia_corrected_pred_mw"] = (
            holdout.loc[valid, "forecast_mw"].to_numpy() + correction
        ).clip(min=0)
    info["predicted_rows"] = int(valid.sum())
    info["status"] = "ok"
    return holdout, info


def benchmark_forecasts(
    holdout: pd.DataFrame,
    prediction_columns: Mapping[str, str] | None = None,
    peak_quantile: float = 0.90,
) -> pd.DataFrame:
    """Compare forecasts on identical rows and one shared peak-demand threshold."""
    if prediction_columns is None:
        prediction_columns = {
            "EIA day-ahead": "forecast_mw",
            "Same hour last week": "seasonal_naive_pred_mw",
            "ML-corrected EIA": "ml_eia_corrected_pred_mw",
        }
    available = {label: col for label, col in prediction_columns.items() if col in holdout}
    if not available:
        return pd.DataFrame()

    common = holdout.dropna(subset=["demand_mw", *available.values()]).copy()
    if common.empty:
        return pd.DataFrame()
    threshold = float(common["demand_mw"].quantile(peak_quantile))
    peak = common[common["demand_mw"] >= threshold]

    rows: list[dict[str, float | int | str]] = []
    for label, column in available.items():
        overall = regression_metrics(common["demand_mw"], common[column])
        peak_metrics = regression_metrics(peak["demand_mw"], peak[column])
        rows.append(
            {
                "model": label,
                "mae_mw": overall["mae"],
                "rmse_mw": overall["rmse"],
                "smape_pct": overall["smape"],
                "peak_mae_mw": peak_metrics["mae"],
                "rows": overall["rows"],
                "peak_rows": peak_metrics["rows"],
                "peak_threshold_mw": threshold,
            }
        )
    return pd.DataFrame(rows)


def promotion_gate(
    benchmark: pd.DataFrame,
    candidate: str = "ML-corrected EIA",
    reference: str = "EIA day-ahead",
) -> dict[str, bool | float | str]:
    """Minimum portfolio gate: beat EIA overall and on peak-hour MAE.

    Passing this gate is necessary, not sufficient. Rolling-origin stability and
    error-slice review should still be required before the model is presented as an
    improvement over the operational forecast.
    """
    if benchmark.empty or not {"model", "mae_mw", "peak_mae_mw"}.issubset(
        benchmark.columns
    ):
        return {"passes": False, "status": "benchmark_unavailable"}
    indexed = benchmark.set_index("model")
    if candidate not in indexed.index or reference not in indexed.index:
        return {"passes": False, "status": "required_model_missing"}

    cand = indexed.loc[candidate]
    ref = indexed.loc[reference]
    required_values = [
        cand["mae_mw"],
        cand["peak_mae_mw"],
        ref["mae_mw"],
        ref["peak_mae_mw"],
    ]
    if any(pd.isna(value) for value in required_values):
        return {"passes": False, "status": "metrics_unavailable"}

    overall_improvement_pct = float(
        (ref["mae_mw"] - cand["mae_mw"]) / ref["mae_mw"] * 100
    )
    peak_improvement_pct = float(
        (ref["peak_mae_mw"] - cand["peak_mae_mw"]) / ref["peak_mae_mw"] * 100
    )
    passes = bool(overall_improvement_pct > 0 and peak_improvement_pct > 0)
    return {
        "passes": passes,
        "status": "passes_minimum_gate" if passes else "does_not_beat_eia",
        "overall_improvement_pct": overall_improvement_pct,
        "peak_improvement_pct": peak_improvement_pct,
    }


def evaluate_eia_residual_candidate(
    df: pd.DataFrame,
    test_start: str | pd.Timestamp,
    peak_quantile: float = 0.90,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    dict[str, bool | float | str],
    dict[str, int | str | float],
]:
    """Fit the first ML candidate and benchmark it against EIA and weekly naive."""
    holdout, info = fit_eia_residual_candidate(df, test_start=test_start)
    benchmark = benchmark_forecasts(holdout, peak_quantile=peak_quantile)
    gate = promotion_gate(benchmark)
    return holdout, benchmark, gate, info
