"""Generate committed GridPulse forecast error-slice tables from prepared PJM data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from gridpulse.forecasting import evaluate_eia_residual_candidate
from gridpulse.slicing import forecast_error_slices, summarize_error_slices


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hourly-path",
        default="data/processed/gridpulse_hourly.parquet",
    )
    parser.add_argument("--respondent", default="PJM")
    parser.add_argument("--test-start", default="2025-01-01")
    parser.add_argument("--output-dir", default="results/error_slices")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.hourly_path)
    if not path.exists():
        raise FileNotFoundError(path)

    frame = pd.read_parquet(path)
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    if "respondent" in frame.columns:
        frame = frame[frame["respondent"].astype(str).eq(args.respondent)].copy()
    frame = frame.dropna(subset=["period"]).sort_values("period")
    if frame.empty:
        raise ValueError(f"No rows found for respondent {args.respondent}")

    holdout, benchmark, gate, model_info = evaluate_eia_residual_candidate(
        frame,
        test_start=args.test_start,
    )
    tables = forecast_error_slices(holdout)
    summary = summarize_error_slices(tables)
    summary.update(
        {
            "respondent": args.respondent,
            "test_start": args.test_start,
            "headline_gate": gate,
            "model_info": model_info,
            "common_rows": int(benchmark["rows"].iloc[0]) if not benchmark.empty else 0,
            "notes": [
                "All slices use rows with complete actual, EIA, and ML predictions.",
                "Calendar slices use PJM local_time when available; otherwise UTC period is used.",
                "Improvement is (EIA MAE - ML MAE) / EIA MAE.",
                "Positive bias means actual demand exceeded the forecast on average.",
            ],
        }
    )

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for key, table in tables.items():
        table.to_csv(output / f"{key}.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))
    for key, table in tables.items():
        print(f"\n=== {key.upper()} ===")
        print(table.to_string(index=False))


if __name__ == "__main__":
    main()
