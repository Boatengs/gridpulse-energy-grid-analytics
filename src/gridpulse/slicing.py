"""Error-slice analysis for GridPulse forecast comparisons."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

REQUIRED_PREDICTION_COLUMNS = {
    "period",
    "demand_mw",
    "forecast_mw",
    "ml_eia_corrected_pred_mw",
}


def _common_prediction_rows(frame: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_PREDICTION_COLUMNS.difference(frame.columns)
    if missing:
        raise ValueError(f"prediction frame is missing columns: {sorted(missing)}")

    work = frame.copy()
    work["period"] = pd.to_datetime(work["period"], utc=True, errors="coerce")
    for col in ["demand_mw", "forecast_mw", "ml_eia_corrected_pred_mw"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work = work.dropna(subset=list(REQUIRED_PREDICTION_COLUMNS)).sort_values("period")

    work["eia_error_mw"] = work["demand_mw"] - work["forecast_mw"]
    work["ml_error_mw"] = work["demand_mw"] - work["ml_eia_corrected_pred_mw"]
    work["eia_abs_error_mw"] = work["eia_error_mw"].abs()
    work["ml_abs_error_mw"] = work["ml_error_mw"].abs()
    return work.reset_index(drop=True)


def _slice_metrics(group: pd.DataFrame) -> pd.Series:
    eia_mae = float(group["eia_abs_error_mw"].mean())
    ml_mae = float(group["ml_abs_error_mw"].mean())
    improvement = np.nan if eia_mae == 0 else (eia_mae - ml_mae) / eia_mae * 100.0
    return pd.Series(
        {
            "rows": int(len(group)),
            "eia_mae_mw": eia_mae,
            "ml_mae_mw": ml_mae,
            "improvement_pct": float(improvement),
            "eia_bias_mw": float(group["eia_error_mw"].mean()),
            "ml_bias_mw": float(group["ml_error_mw"].mean()),
            "eia_underforecast_rate_pct": float((group["eia_error_mw"] > 0).mean() * 100.0),
            "ml_underforecast_rate_pct": float((group["ml_error_mw"] > 0).mean() * 100.0),
        }
    )


def _aggregate(work: pd.DataFrame, column: str, *, name: str) -> pd.DataFrame:
    result = (
        work.groupby(column, observed=True, sort=True)
        .apply(_slice_metrics, include_groups=False)
        .reset_index()
        .rename(columns={column: "slice"})
    )
    result.insert(0, "dimension", name)
    return result


def forecast_error_slices(
    frame: pd.DataFrame,
    *,
    demand_deciles: int = 10,
) -> dict[str, pd.DataFrame]:
    """Compare EIA and ML errors across operationally useful holdout slices.

    Every table is computed from the same rows with complete actual, EIA, and ML values.
    If `local_time` is available it is used for calendar slices; otherwise UTC `period`
    is used and the returned dimension names say so.
    """
    if demand_deciles < 2 or demand_deciles > 20:
        raise ValueError("demand_deciles must be between 2 and 20")

    work = _common_prediction_rows(frame)
    if work.empty:
        empty = pd.DataFrame(
            columns=[
                "dimension",
                "slice",
                "rows",
                "eia_mae_mw",
                "ml_mae_mw",
                "improvement_pct",
                "eia_bias_mw",
                "ml_bias_mw",
                "eia_underforecast_rate_pct",
                "ml_underforecast_rate_pct",
            ]
        )
        return {key: empty.copy() for key in ["hour", "month", "season", "day_type", "demand_decile"]}

    if "local_time" in work.columns:
        calendar = pd.to_datetime(work["local_time"], errors="coerce")
        calendar_basis = "PJM local"
    else:
        calendar = work["period"].dt.tz_convert("UTC").dt.tz_localize(None)
        calendar_basis = "UTC"

    work["hour_slice"] = calendar.dt.hour.astype("Int64")
    work["month_number"] = calendar.dt.month.astype("Int64")
    work["month_slice"] = calendar.dt.strftime("%b")
    work["day_type_slice"] = np.where(calendar.dt.dayofweek < 5, "Weekday", "Weekend")

    season_lookup = {
        12: "DJF",
        1: "DJF",
        2: "DJF",
        3: "MAM",
        4: "MAM",
        5: "MAM",
        6: "JJA",
        7: "JJA",
        8: "JJA",
        9: "SON",
        10: "SON",
        11: "SON",
    }
    work["season_slice"] = work["month_number"].map(season_lookup)

    labels = [f"D{i}" for i in range(1, demand_deciles + 1)]
    ranked = work["demand_mw"].rank(method="first")
    work["demand_decile_slice"] = pd.qcut(ranked, q=demand_deciles, labels=labels)

    hour = _aggregate(work.dropna(subset=["hour_slice"]), "hour_slice", name=f"Hour ({calendar_basis})")
    hour["slice"] = hour["slice"].astype(int)

    month = _aggregate(work.dropna(subset=["month_slice"]), "month_slice", name=f"Month ({calendar_basis})")
    month_order = {month: i for i, month in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}
    month["_order"] = month["slice"].map(month_order)
    month = month.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    season = _aggregate(work.dropna(subset=["season_slice"]), "season_slice", name=f"Season ({calendar_basis})")
    season["_order"] = season["slice"].map({"DJF": 1, "MAM": 2, "JJA": 3, "SON": 4})
    season = season.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    day_type = _aggregate(work, "day_type_slice", name=f"Day type ({calendar_basis})")
    day_type["_order"] = day_type["slice"].map({"Weekday": 1, "Weekend": 2})
    day_type = day_type.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    demand_decile = _aggregate(work, "demand_decile_slice", name="Demand decile")
    demand_decile["_order"] = demand_decile["slice"].astype(str).str.removeprefix("D").astype(int)
    demand_decile = demand_decile.sort_values("_order").drop(columns="_order").reset_index(drop=True)

    return {
        "hour": hour,
        "month": month,
        "season": season,
        "day_type": day_type,
        "demand_decile": demand_decile,
    }


def summarize_error_slices(tables: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Create compact strongest/weakest-improvement findings for committed results."""
    summary: dict[str, Any] = {}
    for key, table in tables.items():
        valid = table.dropna(subset=["improvement_pct"]).copy()
        if valid.empty:
            summary[key] = {"rows": 0, "weakest": None, "strongest": None}
            continue
        weakest = valid.loc[valid["improvement_pct"].idxmin()]
        strongest = valid.loc[valid["improvement_pct"].idxmax()]
        summary[key] = {
            "rows": int(valid["rows"].sum()),
            "weakest": {
                "slice": str(weakest["slice"]),
                "improvement_pct": float(weakest["improvement_pct"]),
                "eia_mae_mw": float(weakest["eia_mae_mw"]),
                "ml_mae_mw": float(weakest["ml_mae_mw"]),
                "rows": int(weakest["rows"]),
            },
            "strongest": {
                "slice": str(strongest["slice"]),
                "improvement_pct": float(strongest["improvement_pct"]),
                "eia_mae_mw": float(strongest["eia_mae_mw"]),
                "ml_mae_mw": float(strongest["ml_mae_mw"]),
                "rows": int(strongest["rows"]),
            },
        }

    deciles = tables.get("demand_decile", pd.DataFrame())
    if not deciles.empty:
        top = deciles[deciles["slice"].astype(str).eq("D10")]
        if not top.empty:
            row = top.iloc[0]
            summary["highest_demand_decile"] = {
                "slice": "D10",
                "improvement_pct": float(row["improvement_pct"]),
                "eia_mae_mw": float(row["eia_mae_mw"]),
                "ml_mae_mw": float(row["ml_mae_mw"]),
                "rows": int(row["rows"]),
            }
    return summary
