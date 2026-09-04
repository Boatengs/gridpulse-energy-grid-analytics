"""Rolling-origin validation for GridPulse forecasting candidates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from gridpulse.forecasting import (
    benchmark_forecasts,
    fit_eia_residual_candidate,
    promotion_gate,
)


def _utc_timestamp(value: str | pd.Timestamp) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def rolling_origin_evaluation(
    df: pd.DataFrame,
    evaluation_start: str | pd.Timestamp,
    horizon_days: int = 30,
    step_days: int = 30,
    peak_quantile: float = 0.90,
    min_train_rows: int = 24 * 90,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Evaluate EIA, weekly naive, and ML across expanding-window future folds.

    Each fold trains only on observations before the fold start. Forecasts are then
    compared on one common row set within the fold horizon using one shared peak
    threshold. The function returns a long benchmark table plus one summary row per
    fold so stability can be inspected instead of inferred from a single holdout.
    """
    if horizon_days <= 0 or step_days <= 0:
        raise ValueError("horizon_days and step_days must be positive integers")

    work = df.copy()
    work["period"] = pd.to_datetime(work["period"], utc=True, errors="coerce")
    work = work.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)
    if work.empty:
        return pd.DataFrame(), pd.DataFrame()

    fold_start = _utc_timestamp(evaluation_start)
    data_end = work["period"].max() + pd.Timedelta(hours=1)
    horizon = pd.Timedelta(days=horizon_days)
    step = pd.Timedelta(days=step_days)

    benchmark_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, object]] = []
    fold_id = 1

    while fold_start < data_end:
        fold_end = min(fold_start + horizon, data_end)
        scoped = work[work["period"] < fold_end].copy()
        holdout, model_info = fit_eia_residual_candidate(
            scoped,
            test_start=fold_start,
            min_train_rows=min_train_rows,
        )
        holdout = holdout[holdout["period"] < fold_end].copy()
        benchmark = benchmark_forecasts(holdout, peak_quantile=peak_quantile)
        gate = promotion_gate(benchmark)

        if not benchmark.empty:
            benchmark = benchmark.copy()
            benchmark.insert(0, "fold_id", fold_id)
            benchmark.insert(1, "fold_start", fold_start)
            benchmark.insert(2, "fold_end", fold_end)
            benchmark_parts.append(benchmark)

        indexed = benchmark.set_index("model") if not benchmark.empty else pd.DataFrame()
        eia = indexed.loc["EIA day-ahead"] if not indexed.empty and "EIA day-ahead" in indexed.index else None
        ml = indexed.loc["ML-corrected EIA"] if not indexed.empty and "ML-corrected EIA" in indexed.index else None

        fold_rows.append(
            {
                "fold_id": fold_id,
                "fold_start": fold_start,
                "fold_end": fold_end,
                "model_status": model_info.get("status", "unknown"),
                "train_rows": int(model_info.get("train_rows", 0)),
                "test_rows": int(model_info.get("test_rows", 0)),
                "predicted_rows": int(model_info.get("predicted_rows", 0)),
                "passes_eia_gate": bool(gate.get("passes", False)),
                "gate_status": gate.get("status", "benchmark_unavailable"),
                "overall_improvement_pct": gate.get("overall_improvement_pct", np.nan),
                "peak_improvement_pct": gate.get("peak_improvement_pct", np.nan),
                "eia_mae_mw": np.nan if eia is None else float(eia["mae_mw"]),
                "ml_mae_mw": np.nan if ml is None else float(ml["mae_mw"]),
                "eia_peak_mae_mw": np.nan if eia is None else float(eia["peak_mae_mw"]),
                "ml_peak_mae_mw": np.nan if ml is None else float(ml["peak_mae_mw"]),
            }
        )

        fold_id += 1
        fold_start = fold_start + step

    benchmarks = pd.concat(benchmark_parts, ignore_index=True) if benchmark_parts else pd.DataFrame()
    folds = pd.DataFrame(fold_rows)
    return benchmarks, folds


def summarize_rolling_origin(folds: pd.DataFrame) -> dict[str, object]:
    """Return transparent stability statistics without inventing a new promotion rule."""
    if folds.empty:
        return {
            "folds": 0,
            "valid_folds": 0,
            "folds_beating_eia": 0,
            "pass_rate_pct": np.nan,
            "all_valid_folds_beat_eia": False,
        }

    valid = folds[
        folds["overall_improvement_pct"].notna() & folds["peak_improvement_pct"].notna()
    ].copy()
    if valid.empty:
        return {
            "folds": int(len(folds)),
            "valid_folds": 0,
            "folds_beating_eia": 0,
            "pass_rate_pct": np.nan,
            "all_valid_folds_beat_eia": False,
        }

    passes = valid["passes_eia_gate"].astype(bool)
    return {
        "folds": int(len(folds)),
        "valid_folds": int(len(valid)),
        "folds_beating_eia": int(passes.sum()),
        "pass_rate_pct": float(passes.mean() * 100),
        "all_valid_folds_beat_eia": bool(passes.all()),
        "median_overall_improvement_pct": float(valid["overall_improvement_pct"].median()),
        "median_peak_improvement_pct": float(valid["peak_improvement_pct"].median()),
        "worst_overall_improvement_pct": float(valid["overall_improvement_pct"].min()),
        "worst_peak_improvement_pct": float(valid["peak_improvement_pct"].min()),
    }
