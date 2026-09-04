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

    plt.figure(figsize=(11, 5.5))
    plt.plot(week["period"], week["demand_mw"], label="Actual demand")
    plt.plot(week["period"], week["forecast_mw"], label="EIA day-ahead forecast")
    plt.axvline(peak_period, linestyle="--", linewidth=1)
    plt.title("PJM demand vs day-ahead forecast around the 2025 annual peak")
    plt.ylabel("MW")
    plt.legend()
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.tight_layout()
    plt.savefig(FIGURES / "pjm_2025_peak_demand_forecast.svg")
    plt.close()

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
    plt.figure(figsize=(9, 5.5))
    plt.bar(x - width / 2, [eia["mae"], naive["mae"]], width, label="All-hour MAE")
    plt.bar(
        x + width / 2,
        [eia_peak["mae"], naive_peak["mae"]],
        width,
        label="Top-decile demand MAE",
    )
    plt.xticks(x, ["EIA day-ahead", "Same hour last week"])
    plt.ylabel("MAE (MW)")
    plt.title("2025 holdout: reported day-ahead forecast vs weekly-naive baseline")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURES / "pjm_2025_forecast_benchmark.svg")
    plt.close()

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
    plt.figure(figsize=(11, 6))
    plt.stackplot(
        june.index,
        *[june[c].fillna(0).values for c in selected],
        labels=[c.replace("_", " ").title() for c in selected],
    )
    plt.ylabel("Daily mean generation (MW)")
    plt.title("PJM reported generation mix — June 2025")
    plt.legend(loc="upper left", ncol=2, fontsize=8)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.tight_layout()
    plt.savefig(FIGURES / "pjm_2025_june_generation_mix.svg")
    plt.close()


if __name__ == "__main__":
    main()
