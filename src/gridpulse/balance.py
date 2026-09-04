"""Ingestion for EIA-930 six-month BALANCE CSV files.

These files are wide, contain every balancing authority, and changed fuel-column
detail in mid-2024. GridPulse filters before concatenation and normalizes both
schemas into one PJM-ready hourly table plus a long fuel-mix table.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import re

import numpy as np
import pandas as pd


def _clean_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


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
        raise FileNotFoundError("No EIA-930 BALANCE CSV files were found.")
    return paths


def _read_balance_rows(
    source: str | Path | Iterable[str | Path],
    respondent: str,
    chunksize: int = 150_000,
) -> pd.DataFrame:
    """Read only the requested balancing authority from large all-BA files."""
    wanted = respondent.strip().upper()
    pieces: list[pd.DataFrame] = []
    for path in _resolve_paths(source):
        for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
            if "Balancing Authority" not in chunk.columns:
                raise ValueError(f"{path.name} is not an EIA-930 BALANCE file.")
            mask = chunk["Balancing Authority"].astype(str).str.strip().str.upper().eq(wanted)
            if mask.any():
                selected = chunk.loc[mask].copy()
                selected["source_file"] = path.name
                pieces.append(selected)
    if not pieces:
        raise ValueError(f"No rows were found for balancing authority {wanted}.")
    raw = pd.concat(pieces, ignore_index=True, sort=False)
    raw.columns = [_clean_name(c) for c in raw.columns]
    return raw


def _numeric(raw: pd.DataFrame, *candidates: str) -> pd.Series:
    """Coalesce numeric candidates in priority order."""
    out = pd.Series(np.nan, index=raw.index, dtype="float64")
    for candidate in candidates:
        if candidate in raw.columns:
            values = pd.to_numeric(raw[candidate], errors="coerce")
            out = out.where(out.notna(), values)
    return out


def _combine_new_or_old(
    raw: pd.DataFrame,
    new_columns: tuple[str, ...],
    old_column: str,
) -> pd.Series:
    """Prefer the post-2024 detailed columns; otherwise use the legacy total."""
    present = [c for c in new_columns if c in raw.columns]
    if present:
        parts = [pd.to_numeric(raw[c], errors="coerce") for c in present]
        new_available = pd.concat(parts, axis=1).notna().any(axis=1)
        new_sum = pd.concat(parts, axis=1).fillna(0).sum(axis=1)
    else:
        new_available = pd.Series(False, index=raw.index)
        new_sum = pd.Series(np.nan, index=raw.index)
    legacy = (
        pd.to_numeric(raw[old_column], errors="coerce")
        if old_column in raw.columns
        else pd.Series(np.nan, index=raw.index)
    )
    return legacy.where(~new_available, new_sum)


def load_balance_exports(
    source: str | Path | Iterable[str | Path],
    respondent: str = "PJM",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize EIA-930 BALANCE files into hourly operating and fuel tables."""
    raw = _read_balance_rows(source, respondent=respondent)

    required = {"utc_time_at_end_of_hour", "balancing_authority", "demand_forecast_mw"}
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError("BALANCE export is missing required columns: " + ", ".join(missing))

    hourly = pd.DataFrame(
        {
            "period": pd.to_datetime(raw["utc_time_at_end_of_hour"], utc=True, errors="coerce"),
            "local_time": pd.to_datetime(raw.get("local_time_at_end_of_hour"), errors="coerce", format="mixed"),
            "hour_number": pd.to_numeric(raw.get("hour_number"), errors="coerce"),
            "respondent": raw["balancing_authority"].astype(str).str.strip(),
            "region": raw.get("region", pd.Series("", index=raw.index)).astype(str).str.strip(),
            "forecast_mw": _numeric(raw, "demand_forecast_mw"),
            "demand_mw": _numeric(raw, "demand_mw_adjusted", "demand_mw"),
            "net_generation_mw": _numeric(raw, "net_generation_mw_adjusted", "net_generation_mw"),
            "total_interchange_mw": _numeric(raw, "total_interchange_mw_adjusted", "total_interchange_mw"),
            "demand_imputed": _numeric(raw, "demand_mw_imputed").notna(),
            "generation_imputed": _numeric(raw, "net_generation_mw_imputed").notna(),
            "interchange_imputed": _numeric(raw, "total_interchange_mw_imputed").notna(),
            "source_file": raw["source_file"].astype(str),
        }
    )

    fuel = pd.DataFrame(index=raw.index)
    fuel["coal"] = _numeric(raw, "net_generation_mw_from_coal_adjusted")
    fuel["natural_gas"] = _numeric(raw, "net_generation_mw_from_natural_gas_adjusted")
    fuel["nuclear"] = _numeric(raw, "net_generation_mw_from_nuclear_adjusted")
    fuel["petroleum"] = _numeric(raw, "net_generation_mw_from_all_petroleum_products_adjusted")
    fuel["other_fuel"] = _numeric(raw, "net_generation_mw_from_other_fuel_sources_adjusted")
    fuel["unknown_fuel"] = _numeric(raw, "net_generation_mw_from_unknown_fuel_sources_adjusted")
    fuel["hydro_pumped"] = _combine_new_or_old(
        raw,
        ("net_generation_mw_from_hydropower_excluding_pumped_storage_adjusted", "net_generation_mw_from_pumped_storage_adjusted"),
        "net_generation_mw_from_hydropower_and_pumped_storage_adjusted",
    )
    fuel["solar"] = _combine_new_or_old(
        raw,
        (
            "net_generation_mw_from_solar_without_integrated_battery_storage_adjusted",
            "net_generation_mw_from_solar_with_integrated_battery_storage_adjusted",
            "net_generation_mw_from_solar_witho_integrated_battery_storage_adjusted",
        ),
        "net_generation_mw_from_solar_adjusted",
    )
    fuel["wind"] = _combine_new_or_old(
        raw,
        ("net_generation_mw_from_wind_without_integrated_battery_storage_adjusted", "net_generation_mw_from_wind_with_integrated_battery_storage_adjusted"),
        "net_generation_mw_from_wind_adjusted",
    )
    fuel["battery_storage"] = _numeric(raw, "net_generation_mw_from_battery_storage_adjusted")
    fuel["other_storage"] = _numeric(raw, "net_generation_mw_from_other_energy_storage_adjusted")
    fuel["geothermal"] = _numeric(raw, "net_generation_mw_from_geothermal_adjusted")

    hourly = (
        hourly.dropna(subset=["period"])
        .sort_values(["respondent", "period"])
        .drop_duplicates(["respondent", "period"], keep="last")
        .reset_index(drop=True)
    )

    fuel["period"] = pd.to_datetime(raw["utc_time_at_end_of_hour"], utc=True, errors="coerce")
    fuel["respondent"] = raw["balancing_authority"].astype(str).str.strip()
    fuel_long = fuel.melt(id_vars=["period", "respondent"], var_name="fuel_type", value_name="generation_mw")
    fuel_long = (
        fuel_long.dropna(subset=["period", "generation_mw"])
        .sort_values(["respondent", "period", "fuel_type"])
        .drop_duplicates(["respondent", "period", "fuel_type"], keep="last")
        .reset_index(drop=True)
    )
    return hourly, fuel_long
