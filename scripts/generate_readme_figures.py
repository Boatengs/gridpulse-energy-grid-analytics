from pathlib import Path
import sys

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gridpulse.demo import make_demo_data
from gridpulse.features import add_operational_features
from gridpulse.stress import add_stress_score


def main() -> None:
    figures = ROOT / "figures"
    figures.mkdir(exist_ok=True)
    df = add_stress_score(add_operational_features(make_demo_data(hours=24 * 14)))

    tail = df.tail(24 * 7)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(tail["period"], tail["demand_mwh"], label="Actual demand")
    ax.plot(tail["period"], tail["forecast_mwh"], label="Day-ahead forecast", alpha=0.8)
    ax.set_title("GridPulse development view — demand vs forecast")
    ax.set_ylabel("MWh")
    ax.legend(frameon=False)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(figures / "demo_demand_forecast.svg", format="svg")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.plot(tail["period"], tail["stress_score"])
    ax.axhline(65, linestyle="--", linewidth=1)
    ax.set_ylim(0, 100)
    ax.set_title("GridPulse development view — operational stress screening")
    ax.set_ylabel("Screening score")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(figures / "demo_stress_timeline.svg", format="svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
