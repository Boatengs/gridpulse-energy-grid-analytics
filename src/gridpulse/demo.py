"""Deterministic synthetic fixture used only when real EIA data are unavailable."""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_demo_data(hours: int = 24 * 30, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    period = pd.date_range("2026-07-01", periods=hours, freq="h", tz="UTC")
    hour = period.hour.to_numpy()
    dow = period.dayofweek.to_numpy()
    daily = 8500 * np.sin((hour - 8) / 24 * 2 * np.pi)
    weekly = np.where(dow < 5, 3500, -2500)
    trend = np.linspace(0, 2500, hours)
    noise = rng.normal(0, 1800, hours)
    demand = 82000 + daily + weekly + trend + noise
    forecast = demand + rng.normal(0, 2600, hours)
    net_generation = demand + rng.normal(800, 1400, hours)
    interchange = net_generation - demand
    return pd.DataFrame(
        {
            "period": period,
            "respondent": "DEMO",
            "respondent_name": "Synthetic development fixture",
            "demand_mw": demand.round(1),
            "forecast_mw": forecast.round(1),
            "net_generation_mw": net_generation.round(1),
            "total_interchange_mw": interchange.round(1),
        }
    )
