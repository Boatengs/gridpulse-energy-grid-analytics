"""Transparent operational-stress screening, not an official reliability metric."""
from __future__ import annotations

import numpy as np
import pandas as pd


def add_stress_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Each component is scaled to 0-1 so the final score remains interpretable.
    demand = out.get("demand_percentile", pd.Series(0.0, index=out.index)).fillna(0).clip(0, 1)
    forecast = out.get("forecast_error_percentile", pd.Series(0.0, index=out.index)).fillna(0).clip(0, 1)

    ramp = out.get("demand_ramp_pct", pd.Series(0.0, index=out.index)).abs().fillna(0)
    ramp_scale = ramp.quantile(0.95) or 1.0
    ramp_component = (ramp / ramp_scale).clip(0, 1)

    interchange = out.get("interchange_percentile", pd.Series(0.0, index=out.index)).fillna(0).clip(0, 1)

    out["stress_score"] = (
        0.40 * demand
        + 0.25 * forecast
        + 0.20 * ramp_component
        + 0.15 * interchange
    ) * 100

    out["stress_band"] = pd.cut(
        out["stress_score"],
        bins=[-np.inf, 45, 65, 80, np.inf],
        labels=["normal", "elevated", "high", "very_high"],
        right=False,
    ).astype(str)
    return out
