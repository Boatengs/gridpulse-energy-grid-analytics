"""Local-file ingestion for downloaded EIA-930 exports.

The loader accepts one CSV, several CSVs, or a directory of CSVs. It supports
both EIA's long-form exports and GridPulse's already-wide hourly schema.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

import pandas as pd

REGION_TYPE_MAP = {
    "D": "demand_mwh",
    "DF": "forecast_mwh",
    "NG": "net_generation_mwh",
    "TI": "total_interchange_mwh",
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
    cleaned = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower())
    return cleaned.strip("_")


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
    frames = [pd.read_csv(path, low_memory=False) for path in _resolve_paths(source)]
    return pd.concat(frames, ignore_index=True, sort=False)


def _find_column(columns: Iterable[str], *candidates: str) -> str | None:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def load_region_exports(source: str | Path | Iterable[str | Path]) -> pd.DataFrame:
    """Load downloaded EIA region-data CSV exports into one hourly wide table."""
    raw = _normalize_columns(_read_csvs(source))

    if {"period", "demand_mwh"}.issubset(raw.columns):
        out = raw.copy()
        out["period"] = pd.to_datetime(out["period"], utc=True, errors="coerce")
        for column in REGION_TYPE_MAP.values():
            if column in out:
                out[column] = pd.to_numeric(out[column], errors="coerce")
        if "respondent" not in out:
            out["respondent"] = "UNKNOWN"
        if "respondent_name" not in out:
            out["respondent_name"] = out["respondent"]
        return (
            out.dropna(subset=["period"])
            .sort_values(["respondent", "period"])
            .drop_duplicates(["respondent", "period"], keep="last")
            .reset_index(drop=True)
        )

    period_col = _find_column(raw.columns, "period", "datetime", "timestamp")
    respondent_col = _find_column(raw.columns, "respondent", "balancing_authority", "ba")
    respondent_name_col = _find_column(
        raw.columns, "respondent_name", "balancing_authority_name", "ba_name"
    )
    type_col = _find_column(raw.columns, "type", "type_code")
    type_name_col = _find_column(raw.columns, "type_name", "series_description", "series_name")
    value_col = _find_column(raw.columns, "value", "value_mwh", "mwh")

    required = {"period": period_col, "respondent": respondent_col, "value": value_col}
    missing = [label for label, column in required.items() if column is None]
    if missing:
        raise ValueError(
            "Downloaded EIA region-data export is missing required fields: "
            + ", ".join(missing)
        )
    if type_col is None and type_name_col is None:
        raise ValueError("Downloaded EIA export needs either a type/type_code or type_name field.")

    work = pd.DataFrame(
        {
            "period": pd.to_datetime(raw[period_col], utc=True, errors="coerce"),
            "respondent": raw[respondent_col].astype(str).str.strip(),
            "respondent_name": (
                raw[respondent_name_col].astype(str).str.strip()
                if respondent_name_col
                else raw[respondent_col].astype(str).str.strip()
            ),
            "value": pd.to_numeric(raw[value_col], errors="coerce"),
        }
    )

    if type_col:
        type_code = raw[type_col].astype(str).str.strip().str.upper()
    else:
        type_code = pd.Series("", index=raw.index, dtype="object")

    if type_name_col:
        normalized_names = raw[type_name_col].astype(str).str.strip().str.lower()
        inferred = normalized_names.map(TYPE_NAME_MAP)
        type_code = type_code.where(type_code.isin(REGION_TYPE_MAP), inferred)

    work["type"] = type_code
    work = work[
        work["type"].isin(REGION_TYPE_MAP)
        & work["period"].notna()
        & work["value"].notna()
    ].copy()

    if work.empty:
        raise ValueError(
            "No D/DF/NG/TI hourly rows were found in the downloaded EIA region-data export."
        )

    duplicate_keys = ["period", "respondent", "type"]
    if work.duplicated(duplicate_keys).any():
        work = work.drop_duplicates(duplicate_keys, keep="last")

    wide = (
        work.pivot(
            index=["period", "respondent", "respondent_name"],
            columns="type",
            values="value",
        )
        .reset_index()
        .rename(columns=REGION_TYPE_MAP)
    )
    wide.columns.name = None
    return wide.sort_values(["respondent", "period"]).reset_index(drop=True)


def load_fuel_exports(source: str | Path | Iterable[str | Path]) -> pd.DataFrame:
    """Load downloaded EIA hourly fuel-type exports into a canonical long table."""
    raw = _normalize_columns(_read_csvs(source))

    period_col = _find_column(raw.columns, "period", "datetime", "timestamp")
    respondent_col = _find_column(raw.columns, "respondent", "balancing_authority", "ba")
    respondent_name_col = _find_column(
        raw.columns, "respondent_name", "balancing_authority_name", "ba_name"
    )
    fuel_col = _find_column(raw.columns, *FUEL_COLUMN_CANDIDATES)
    value_col = _find_column(raw.columns, "value", "generation_mwh", "mwh")

    required = {
        "period": period_col,
        "respondent": respondent_col,
        "fuel type": fuel_col,
        "value": value_col,
    }
    missing = [label for label, column in required.items() if column is None]
    if missing:
        raise ValueError(
            "Downloaded EIA fuel-type export is missing required fields: "
            + ", ".join(missing)
        )

    out = pd.DataFrame(
        {
            "period": pd.to_datetime(raw[period_col], utc=True, errors="coerce"),
            "respondent": raw[respondent_col].astype(str).str.strip(),
            "respondent_name": (
                raw[respondent_name_col].astype(str).str.strip()
                if respondent_name_col
                else raw[respondent_col].astype(str).str.strip()
            ),
            "fuel_type": raw[fuel_col].astype(str).str.strip(),
            "generation_mwh": pd.to_numeric(raw[value_col], errors="coerce"),
        }
    )
    out = out.dropna(subset=["period", "generation_mwh"])
    out = out[out["fuel_type"].ne("")].copy()
    out = out.drop_duplicates(["period", "respondent", "fuel_type"], keep="last")
    return out.sort_values(["respondent", "period", "fuel_type"]).reset_index(drop=True)


def hourly_qa_summary(df: pd.DataFrame) -> dict[str, int | float | str | None]:
    """Return a compact, human-readable QA summary for a processed hourly table."""
    if df.empty:
        return {
            "rows": 0,
            "respondents": 0,
            "start": None,
            "end": None,
            "duplicate_hours": 0,
            "missing_demand": 0,
            "nonpositive_demand": 0,
            "missing_hour_slots": 0,
        }

    work = df.copy()
    work["period"] = pd.to_datetime(work["period"], utc=True, errors="coerce")
    duplicate_hours = int(work.duplicated(["respondent", "period"]).sum())
    missing_demand = int(work["demand_mwh"].isna().sum()) if "demand_mwh" in work else len(work)
    nonpositive_demand = (
        int((pd.to_numeric(work["demand_mwh"], errors="coerce") <= 0).sum())
        if "demand_mwh" in work
        else 0
    )

    missing_slots = 0
    for _, group in work.dropna(subset=["period"]).groupby("respondent"):
        if group.empty:
            continue
        expected = pd.date_range(group["period"].min(), group["period"].max(), freq="h", tz="UTC")
        missing_slots += max(0, len(expected) - group["period"].nunique())

    return {
        "rows": int(len(work)),
        "respondents": int(work["respondent"].nunique()),
        "start": work["period"].min().isoformat() if work["period"].notna().any() else None,
        "end": work["period"].max().isoformat() if work["period"].notna().any() else None,
        "duplicate_hours": duplicate_hours,
        "missing_demand": missing_demand,
        "nonpositive_demand": nonpositive_demand,
        "missing_hour_slots": int(missing_slots),
    }


def save_processed(
    region_data: pd.DataFrame,
    output_dir: str | Path,
    fuel_data: pd.DataFrame | None = None,
) -> tuple[Path, Path | None]:
    """Write compact Parquet tables used by the dashboard and modeling pipeline."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    hourly_path = output / "gridpulse_hourly.parquet"
    region_data.to_parquet(hourly_path, index=False)

    fuel_path: Path | None = None
    if fuel_data is not None and not fuel_data.empty:
        fuel_path = output / "gridpulse_fuel_mix.parquet"
        fuel_data.to_parquet(fuel_path, index=False)
    return hourly_path, fuel_path
