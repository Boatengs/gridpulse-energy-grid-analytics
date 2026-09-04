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
