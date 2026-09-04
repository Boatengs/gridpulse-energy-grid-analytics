"""Local-file utilities for downloaded EIA-930 data."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

import pandas as pd

REGION_TYPE_MAP = {
    "D": "demand_mw",
    "DF": "forecast_mw",
    "NG": "net_generation_mw",
    "TI": "total_interchange_mw",
}
TYPE_NAME_MAP = {
    "demand": "D",
    "demand forecast": "DF",
    "day-ahead demand forecast": "DF",
    "day ahead demand forecast": "DF",
    "net generation": "NG",
    "total interchange": "TI",
    "interchange": "TI",
}
FUEL_COLUMN_CANDIDATES = (
    "fueltype",
    "fuel_type",
    "fueltype_name",
    "fuel_type_name",
    "type_name",
)


def _clean_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = [_clean_name(c) for c in out.columns]
    return out


def _resolve_paths(source: str | Path | Iterable[str | Path]) -> list[Path]:
    if isinstance(source, (str, Path)):
        source = [source]
    paths: list[Path] = []
    for item in source:
        path = Path(item)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.csv")))
        elif path.suffix.lower() == ".csv":
            paths.append(path)
    if not paths:
        raise FileNotFoundError("No CSV files were found in the supplied EIA source.")
    return paths


def _read_csvs(source: str | Path | Iterable[str | Path]) -> pd.DataFrame:
    return pd.concat(
        [pd.read_csv(path, low_memory=False) for path in _resolve_paths(source)],
        ignore_index=True,
        sort=False,
    )


def _find_column(columns: Iterable[str], *candidates: str) -> str | None:
    available = set(columns)
    return next((candidate for candidate in candidates if candidate in available), None)


def load_region_exports(source: str | Path | Iterable[str | Path]) -> pd.DataFrame:
    """Load long-form EIA API/browser exports into one hourly wide table.

    For official six-month BALANCE files, use gridpulse.balance.load_balance_exports.
    """
    raw = _normalize_columns(_read_csvs(source))

    if {"period", "demand_mw"}.issubset(raw.columns):
        out = raw.copy()
        out["period"] = pd.to_datetime(out["period"], utc=True, errors="coerce")
        for column in REGION_TYPE_MAP.values():
            if column in out:
                out[column] = pd.to_numeric(out[column], errors="coerce")
        if "respondent" not in out:
            out["respondent"] = "UNKNOWN"
        return (
            out.dropna(subset=["period"])
            .sort_values(["respondent", "period"])
            .drop_duplicates(["respondent", "period"], keep="last")
            .reset_index(drop=True)
        )

    period_col = _find_column(raw.columns, "period", "datetime", "timestamp")
    respondent_col = _find_column(raw.columns, "respondent", "balancing_authority", "ba")
    type_col = _find_column(raw.columns, "type", "type_code")
    type_name_col = _find_column(raw.columns, "type_name", "series_description", "series_name")
    value_col = _find_column(raw.columns, "value", "value_mw", "mw", "value_mwh", "mwh")

    required = {"period": period_col, "respondent": respondent_col, "value": value_col}
    missing = [label for label, column in required.items() if column is None]
    if missing:
        raise ValueError("Downloaded EIA region export is missing: " + ", ".join(missing))
    if type_col is None and type_name_col is None:
        raise ValueError("Downloaded EIA export needs a type code or type name.")

    work = pd.DataFrame(
        {
            "period": pd.to_datetime(raw[period_col], utc=True, errors="coerce"),
            "respondent": raw[respondent_col].astype(str).str.strip(),
            "value": pd.to_numeric(raw[value_col], errors="coerce"),
        }
    )
    type_code = (
        raw[type_col].astype(str).str.strip().str.upper()
        if type_col
        else pd.Series("", index=raw.index, dtype="object")
    )
    if type_name_col:
        inferred = raw[type_name_col].astype(str).str.strip().str.lower().map(TYPE_NAME_MAP)
        type_code = type_code.where(type_code.isin(REGION_TYPE_MAP), inferred)
    work["type"] = type_code
    work = work[
        work["type"].isin(REGION_TYPE_MAP)
        & work["period"].notna()
        & work["value"].notna()
    ].drop_duplicates(["period", "respondent", "type"], keep="last")

    if work.empty:
        raise ValueError("No D/DF/NG/TI hourly rows were found in the EIA export.")

    wide = (
        work.pivot(index=["period", "respondent"], columns="type", values="value")
        .reset_index()
        .rename(columns=REGION_TYPE_MAP)
    )
    wide.columns.name = None
    return wide.sort_values(["respondent", "period"]).reset_index(drop=True)


def load_fuel_exports(source: str | Path | Iterable[str | Path]) -> pd.DataFrame:
    """Load long-form EIA fuel exports into period/respondent/fuel/generation_mw."""
    raw = _normalize_columns(_read_csvs(source))
    period_col = _find_column(raw.columns, "period", "datetime", "timestamp")
    respondent_col = _find_column(raw.columns, "respondent", "balancing_authority", "ba")
    fuel_col = _find_column(raw.columns, *FUEL_COLUMN_CANDIDATES)
    value_col = _find_column(raw.columns, "value", "generation_mw", "mw", "generation_mwh", "mwh")
    missing = [
        label
        for label, column in {
            "period": period_col,
            "respondent": respondent_col,
            "fuel type": fuel_col,
            "value": value_col,
        }.items()
        if column is None
    ]
    if missing:
        raise ValueError("Downloaded EIA fuel export is missing: " + ", ".join(missing))

    out = pd.DataFrame(
        {
            "period": pd.to_datetime(raw[period_col], utc=True, errors="coerce"),
            "respondent": raw[respondent_col].astype(str).str.strip(),
            "fuel_type": raw[fuel_col].astype(str).str.strip(),
            "generation_mw": pd.to_numeric(raw[value_col], errors="coerce"),
        }
    )
    return (
        out.dropna(subset=["period", "generation_mw"])
        .loc[lambda x: x["fuel_type"].ne("")]
        .drop_duplicates(["period", "respondent", "fuel_type"], keep="last")
        .sort_values(["respondent", "period", "fuel_type"])
        .reset_index(drop=True)
    )


def hourly_qa_summary(df: pd.DataFrame) -> dict[str, int | float | str | None]:
    """Return compact QA evidence for the processed hourly operating table."""
    if df.empty:
        return {"rows": 0, "respondents": 0, "start": None, "end": None}

    work = df.copy()
    work["period"] = pd.to_datetime(work["period"], utc=True, errors="coerce")
    missing_slots = 0
    for _, group in work.dropna(subset=["period"]).groupby("respondent"):
        expected = pd.date_range(group["period"].min(), group["period"].max(), freq="h", tz="UTC")
        missing_slots += max(0, len(expected) - group["period"].nunique())

    summary: dict[str, int | float | str | None] = {
        "rows": int(len(work)),
        "respondents": int(work["respondent"].nunique()),
        "start": work["period"].min().isoformat() if work["period"].notna().any() else None,
        "end": work["period"].max().isoformat() if work["period"].notna().any() else None,
        "duplicate_hours": int(work.duplicated(["respondent", "period"]).sum()),
        "missing_hour_slots": int(missing_slots),
        "missing_demand": int(work.get("demand_mw", pd.Series(index=work.index, dtype=float)).isna().sum()),
        "missing_forecast": int(work.get("forecast_mw", pd.Series(index=work.index, dtype=float)).isna().sum()),
        "missing_generation": int(work.get("net_generation_mw", pd.Series(index=work.index, dtype=float)).isna().sum()),
        "missing_interchange": int(work.get("total_interchange_mw", pd.Series(index=work.index, dtype=float)).isna().sum()),
        "nonpositive_demand": int((pd.to_numeric(work.get("demand_mw"), errors="coerce") <= 0).sum()) if "demand_mw" in work else 0,
    }
    for flag in ("demand_imputed", "generation_imputed", "interchange_imputed"):
        if flag in work:
            summary[flag] = int(work[flag].fillna(False).astype(bool).sum())
    if "balance_residual_mw" in work:
        residual = pd.to_numeric(work["balance_residual_mw"], errors="coerce").abs()
        summary["max_abs_balance_residual_mw"] = float(residual.max())
        summary["balance_residual_gt_10000_mw"] = int((residual > 10_000).sum())
    if "qa_anomaly" in work:
        summary["qa_anomaly_hours"] = int(work["qa_anomaly"].fillna(False).astype(bool).sum())
    if "qa_isolated_demand_discontinuity" in work:
        summary["qa_isolated_demand_discontinuities"] = int(
            work["qa_isolated_demand_discontinuity"].fillna(False).astype(bool).sum()
        )
    return summary


def save_processed(
    region_data: pd.DataFrame,
    output_dir: str | Path,
    fuel_data: pd.DataFrame | None = None,
) -> tuple[Path, Path | None]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    hourly_path = output / "gridpulse_hourly.parquet"
    region_data.to_parquet(hourly_path, index=False)

    fuel_path: Path | None = None
    if fuel_data is not None and not fuel_data.empty:
        fuel_path = output / "gridpulse_fuel_mix.parquet"
        fuel_data.to_parquet(fuel_path, index=False)
    return hourly_path, fuel_path
