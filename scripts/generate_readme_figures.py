"""Regenerate README figures from prepared PJM EIA-930 data."""
from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gridpulse.forecasting import evaluate_eia_residual_candidate

HOURLY = Path("data/processed/gridpulse_hourly.parquet")
FUEL = Path("data/processed/gridpulse_fuel_mix.parquet")
FIGURES = Path("figures")


def _save_svg(fig: plt.Figure, filename: str) -> None:
    """Save an SVG with enough exterior padding for titles, ticks, and legends."""
    fig.savefig(
        FIGURES / filename,
        format="svg",
        bbox_inches="tight",
        pad_inches=0.2,
    )
    plt.close(fig)


def main() -> None:
    if not HOURLY.exists() or not FUEL.exists():
        raise FileNotFoundError(
            "Prepare the downloaded EIA data first with scripts/prepare_downloaded_eia.py."
        )

    FIGURES.mkdir(exist_ok=True)
    hourly = pd.read_parquet(HOURLY)
    fuel = pd.read_parquet(FUEL)
    hourly["period"] = pd.to_datetime(hourly["period"], utc=True)
    hourly["local_time"] = pd.to_datetime(hourly["local_time"])
    fuel["period"] = pd.to_datetime(fuel["period"], utc=True)

    holdout, benchmark, _, _ = evaluate_eia_residual_candidate(
        hourly,
        test_start="2025-01-01",
        peak_quantile=0.90,
    )

    p2025 = hourly[hourly["local_time"].dt.year.eq(2025)].copy()
    peak = p2025.loc[p2025["demand_mw"].idxmax()]
    peak_period = peak["period"]
    week = hourly[
        hourly["period"].between(
            peak_period - pd.Timedelta(days=3),
            peak_period + pd.Timedelta(days=3),
        )
    ].copy()
    week = week.merge(
        holdout[["period", "ml_eia_corrected_pred_mw"]],
        on="period",
        how="left",
        validate="one_to_one",
    )

    fig, ax = plt.subplots(figsize=(11, 5.8), constrained_layout=True)
    ax.plot(week["period"], week["demand_mw"], label="Actual demand")
    ax.plot(week["period"], week["forecast_mw"], label="EIA day-ahead forecast")
    ax.plot(
        week["period"],
        week["ml_eia_corrected_pred_mw"],
        label="GridPulse ML-corrected EIA",
    )
    ax.axvline(peak_period, linestyle="--", linewidth=1)
    ax.set_title(
        "PJM demand vs EIA and GridPulse forecasts around the 2025 annual peak",
        pad=14,
    )
    ax.set_ylabel("MW")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=3,
        frameon=False,
    )
    _save_svg(fig, "pjm_2025_peak_demand_forecast.svg")

    order = ["EIA day-ahead", "Same hour last week", "ML-corrected EIA"]
    scored = benchmark.set_index("model").loc[order]
    x = np.arange(len(order))
    width = 0.36
    fig, ax = plt.subplots(figsize=(10.5, 6.2), constrained_layout=True)
    ax.bar(
        x - width / 2,
        scored["mae_mw"].to_numpy(),
        width,
        label="All-hour MAE",
    )
    ax.bar(
        x + width / 2,
        scored["peak_mae_mw"].to_numpy(),
        width,
        label="Top-decile demand MAE",
    )
    ax.set_xticks(
        x,
        ["EIA day-ahead", "Same hour\nlast week", "GridPulse ML\ncorrected EIA"],
    )
    ax.set_ylabel("MAE (MW)")
    ax.set_title(
        "2025 holdout forecast benchmark — common rows and shared peak threshold",
        pad=14,
    )
    ax.margins(y=0.12)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=2,
        frameon=False,
    )
    _save_svg(fig, "pjm_2025_forecast_benchmark.svg")

    pivot = fuel.pivot_table(
        index="period", columns="fuel_type", values="generation_mw", aggfunc="sum"
    )
    june = pivot.loc["2025-06-01":"2025-06-30"].resample("D").mean()
    selected = [
        c
        for c in [
            "nuclear",
            "natural_gas",
            "coal",
            "wind",
            "solar",
            "hydro_pumped",
            "petroleum",
            "other_fuel",
        ]
        if c in june.columns
    ]
    fig, ax = plt.subplots(figsize=(11, 6.6), constrained_layout=True)
    ax.stackplot(
        june.index,
        *[june[c].fillna(0).values for c in selected],
        labels=[c.replace("_", " ").title() for c in selected],
    )
    ax.set_ylabel("Daily mean generation (MW)")
    ax.set_title("PJM reported generation mix — June 2025", pad=14)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=4,
        frameon=False,
        fontsize=8,
    )
    _save_svg(fig, "pjm_2025_june_generation_mix.svg")


if __name__ == "__main__":
    main()
