"""Transparent operational-stress screening, not an official reliability metric."""
from __future__ import annotations

import numpy as np
import pandas as pd

COMPONENT_WEIGHTS = {
    "demand_percentile": 0.40,
    "forecast_error_percentile": 0.25,
    "ramp_component": 0.20,
    "interchange_percentile": 0.15,
}


def add_stress_score(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    ramp = out.get("demand_ramp_pct", pd.Series(np.nan, index=out.index)).abs()
    ramp_scale = ramp.quantile(0.95)
    if pd.isna(ramp_scale) or ramp_scale <= 0:
        ramp_scale = 1.0
    out["ramp_component"] = (ramp / ramp_scale).clip(0, 1)

    components = pd.DataFrame(index=out.index)
    for column in ("demand_percentile", "forecast_error_percentile", "interchange_percentile"):
        components[column] = pd.to_numeric(
            out.get(column, pd.Series(np.nan, index=out.index)), errors="coerce"
        ).clip(0, 1)
    components["ramp_component"] = out["ramp_component"]

    weights = pd.Series(COMPONENT_WEIGHTS)
    weighted = components.mul(weights, axis=1)
    available_weight = components.notna().mul(weights, axis=1).sum(axis=1)
    numerator = weighted.sum(axis=1, min_count=1)

    # Missing EIA components should not be interpreted as zero stress.
    out["stress_component_weight"] = available_weight
    out["stress_components_available"] = components.notna().sum(axis=1)
    out["stress_score"] = (numerator / available_weight.replace(0, np.nan)) * 100

    out["stress_band"] = pd.cut(
        out["stress_score"],
        bins=[-np.inf, 45, 65, 80, np.inf],
        labels=["normal", "elevated", "high", "very_high"],
        right=False,
    ).astype("string")
    return out
