"""Feature engineering for hourly electric-grid operating data."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_operational_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy().sort_values("period").reset_index(drop=True)
    out["period"] = pd.to_datetime(out["period"], utc=True)

    # Time features make recurring grid behavior visible before any forecasting model is fit.
    out["hour_utc"] = out["period"].dt.hour
    out["day_of_week"] = out["period"].dt.dayofweek
    out["date"] = out["period"].dt.date

    if "demand_mwh" in out:
        out["demand_change_mwh"] = out["demand_mwh"].diff()
        out["demand_ramp_pct"] = out["demand_mwh"].pct_change() * 100
        out["demand_percentile"] = out["demand_mwh"].rank(pct=True)
        out["rolling_demand_24h"] = out["demand_mwh"].rolling(24, min_periods=6).mean()

    if {"demand_mwh", "forecast_mwh"}.issubset(out.columns):
        out["forecast_error_mwh"] = out["demand_mwh"] - out["forecast_mwh"]
        out["abs_forecast_error_mwh"] = out["forecast_error_mwh"].abs()
        denom = out["demand_mwh"].abs().replace(0, np.nan)
        out["abs_forecast_error_pct"] = out["abs_forecast_error_mwh"] / denom * 100
        out["forecast_error_percentile"] = out["abs_forecast_error_mwh"].rank(pct=True)

    if {"demand_mwh", "total_interchange_mwh"}.issubset(out.columns):
        denom = out["demand_mwh"].abs().replace(0, np.nan)
        out["interchange_share"] = out["total_interchange_mwh"].abs() / denom
        out["interchange_percentile"] = out["interchange_share"].rank(pct=True)

    return out
