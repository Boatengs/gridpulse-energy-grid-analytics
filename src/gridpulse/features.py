"""Feature engineering for hourly electric-grid operating data."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_operational_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values("period").reset_index(drop=True)
    out["period"] = pd.to_datetime(out["period"], utc=True)

    # Time features make recurring grid behavior visible before any model is fit.
    out["hour_utc"] = out["period"].dt.hour
    out["day_of_week"] = out["period"].dt.dayofweek
    out["date"] = out["period"].dt.date

    if "demand_mw" in out:
        out["demand_change_mw"] = out["demand_mw"].diff()
        out["demand_ramp_pct"] = out["demand_mw"].pct_change(fill_method=None) * 100
        out["demand_percentile"] = out["demand_mw"].rank(pct=True)
        out["rolling_demand_24h_mw"] = out["demand_mw"].rolling(24, min_periods=6).mean()

    if {"demand_mw", "forecast_mw"}.issubset(out.columns):
        out["forecast_error_mw"] = out["demand_mw"] - out["forecast_mw"]
        out["abs_forecast_error_mw"] = out["forecast_error_mw"].abs()
        denom = out["demand_mw"].abs().replace(0, np.nan)
        out["abs_forecast_error_pct"] = out["abs_forecast_error_mw"] / denom * 100
        out["forecast_error_percentile"] = out["abs_forecast_error_mw"].rank(pct=True)

    if {"demand_mw", "total_interchange_mw"}.issubset(out.columns):
        denom = out["demand_mw"].abs().replace(0, np.nan)
        out["interchange_share"] = out["total_interchange_mw"].abs() / denom
        out["interchange_percentile"] = out["interchange_share"].rank(pct=True)

    if {"demand_mw", "net_generation_mw", "total_interchange_mw"}.issubset(out.columns):
        # Large departures from the balancing-account identity are kept as QA signals.
        out["balance_residual_mw"] = (
            out["net_generation_mw"] - out["demand_mw"] - out["total_interchange_mw"]
        )

    return out


def add_qa_flags(
    df: pd.DataFrame,
    demand_step_threshold_pct: float = 25.0,
    balance_residual_threshold_mw: float = 10_000.0,
) -> pd.DataFrame:
    """Flag suspicious source-data discontinuities without changing reported values.

    A row is flagged when it is an isolated one-hour demand discontinuity or when a
    large exact-hour demand step coincides with a large generation-demand-interchange
    balance residual. The flags are diagnostic only: no smoothing, clipping,
    interpolation, or deletion is performed.
    """
    out = df.copy()
    out["period"] = pd.to_datetime(out["period"], utc=True)
    if "respondent" not in out:
        out["respondent"] = "UNKNOWN"
    out = out.sort_values(["respondent", "period"]).reset_index(drop=True)

    if "balance_residual_mw" not in out and {
        "demand_mw",
        "net_generation_mw",
        "total_interchange_mw",
    }.issubset(out.columns):
        out["balance_residual_mw"] = (
            out["net_generation_mw"] - out["demand_mw"] - out["total_interchange_mw"]
        )

    if "demand_mw" in out:
        grouped = out.groupby("respondent", sort=False)
        prior_demand = grouped["demand_mw"].shift(1)
        next_demand = grouped["demand_mw"].shift(-1)
        prior_period = grouped["period"].shift(1)
        next_period = grouped["period"].shift(-1)
        exact_prev_hour = (out["period"] - prior_period).eq(pd.Timedelta(hours=1))
        exact_next_hour = (next_period - out["period"]).eq(pd.Timedelta(hours=1))

        out["qa_demand_step_pct"] = ((out["demand_mw"] / prior_demand) - 1) * 100
        out.loc[~exact_prev_hour, "qa_demand_step_pct"] = np.nan
        next_step_pct = ((next_demand / out["demand_mw"]) - 1) * 100
        next_step_pct = next_step_pct.where(exact_next_hour)

        out["qa_large_demand_step"] = out["qa_demand_step_pct"].abs().ge(
            demand_step_threshold_pct
        )
        out["qa_isolated_demand_discontinuity"] = (
            out["qa_demand_step_pct"].abs().ge(demand_step_threshold_pct)
            & next_step_pct.abs().ge(demand_step_threshold_pct)
            & (out["qa_demand_step_pct"] * next_step_pct < 0)
        )
    else:
        out["qa_demand_step_pct"] = np.nan
        out["qa_large_demand_step"] = False
        out["qa_isolated_demand_discontinuity"] = False

    if "balance_residual_mw" in out:
        out["qa_large_balance_residual"] = (
            pd.to_numeric(out["balance_residual_mw"], errors="coerce")
            .abs()
            .ge(balance_residual_threshold_mw)
        )
    else:
        out["qa_large_balance_residual"] = False

    step_and_balance = out["qa_large_demand_step"] & out["qa_large_balance_residual"]
    out["qa_anomaly"] = out["qa_isolated_demand_discontinuity"] | step_and_balance
    out["qa_anomaly_reason"] = np.select(
        [out["qa_isolated_demand_discontinuity"], step_and_balance],
        [
            "isolated one-hour demand discontinuity",
            "large one-hour demand step + large balance residual",
        ],
        default="",
    )
    return out
