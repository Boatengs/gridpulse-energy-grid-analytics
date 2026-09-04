"""Regenerate README figures from prepared PJM EIA-930 data."""
from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gridpulse.forecasting import add_seasonal_naive_prediction, regression_metrics

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

    p2025 = hourly[hourly["local_time"].dt.year.eq(2025)].copy()
    peak = p2025.loc[p2025["demand_mw"].idxmax()]
    peak_period = peak["period"]
    week = hourly[
        hourly["period"].between(
            peak_period - pd.Timedelta(days=3),
            peak_period + pd.Timedelta(days=3),
        )
    ]

    fig, ax = plt.subplots(figsize=(11, 5.8), constrained_layout=True)
    ax.plot(week["period"], week["demand_mw"], label="Actual demand")
    ax.plot(week["period"], week["forecast_mw"], label="EIA day-ahead forecast")
    ax.axvline(peak_period, linestyle="--", linewidth=1)
    ax.set_title("PJM demand vs day-ahead forecast around the 2025 annual peak", pad=14)
    ax.set_ylabel("MW")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.12),
        ncol=2,
        frameon=False,
    )
    _save_svg(fig, "pjm_2025_peak_demand_forecast.svg")

    work = add_seasonal_naive_prediction(hourly)
    holdout = work[work["local_time"].dt.year.eq(2025)].copy()
    eia = regression_metrics(holdout["demand_mw"], holdout["forecast_mw"])
    naive = regression_metrics(holdout["demand_mw"], holdout["seasonal_naive_pred_mw"])
    threshold = holdout["demand_mw"].quantile(0.90)
    peak_hours = holdout[holdout["demand_mw"] >= threshold]
    eia_peak = regression_metrics(peak_hours["demand_mw"], peak_hours["forecast_mw"])
    naive_peak = regression_metrics(
        peak_hours["demand_mw"], peak_hours["seasonal_naive_pred_mw"]
    )

    x = np.arange(2)
    width = 0.36
    fig, ax = plt.subplots(figsize=(9.5, 6.2), constrained_layout=True)
    ax.bar(x - width / 2, [eia["mae"], naive["mae"]], width, label="All-hour MAE")
    ax.bar(
        x + width / 2,
        [eia_peak["mae"], naive_peak["mae"]],
        width,
        label="Top-decile demand MAE",
    )
    ax.set_xticks(x, ["EIA day-ahead", "Same hour\nlast week"])
    ax.set_ylabel("MAE (MW)")
    ax.set_title("2025 holdout: reported day-ahead forecast vs weekly-naive baseline", pad=14)
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
