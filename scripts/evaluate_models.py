"""Evaluate GridPulse forecasts against EIA and write reproducible result tables."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from gridpulse.forecasting import (
    benchmark_forecasts,
    evaluate_eia_residual_candidate,
    promotion_gate,
)
from gridpulse.validation import rolling_origin_evaluation, summarize_rolling_origin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hourly-path",
        default="data/processed/gridpulse_hourly.parquet",
        help="Prepared GridPulse hourly Parquet table.",
    )
    parser.add_argument("--respondent", default="PJM")
    parser.add_argument("--test-start", default="2025-01-01")
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=30)
    parser.add_argument("--peak-quantile", type=float, default=0.90)
    parser.add_argument(
        "--output-dir",
        default="data/processed/model_evaluation",
        help="Directory for CSV/JSON evaluation outputs.",
    )
    return parser.parse_args()


def _jsonable(value: object) -> object:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value) if not isinstance(value, (dict, list, tuple, str, bool)) else False:
        return None
    return value


def main() -> None:
    args = parse_args()
    hourly_path = Path(args.hourly_path)
    if not hourly_path.exists():
        raise FileNotFoundError(f"Prepared hourly data not found: {hourly_path}")

    df = pd.read_parquet(hourly_path)
    df["period"] = pd.to_datetime(df["period"], utc=True, errors="coerce")
    if "respondent" in df.columns:
        df = df[df["respondent"].astype(str).eq(args.respondent)].copy()
    df = df.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)
    if df.empty:
        raise ValueError(f"No hourly rows available for respondent {args.respondent}.")

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)

    holdout, headline, headline_gate, model_info = evaluate_eia_residual_candidate(
        df,
        test_start=args.test_start,
        peak_quantile=args.peak_quantile,
    )
    headline.to_csv(output / "headline_benchmark.csv", index=False)

    sensitivity: pd.DataFrame | None = None
    sensitivity_gate: dict[str, object] | None = None
    if "qa_anomaly" in holdout.columns:
        score_rows = holdout[~holdout["qa_anomaly"].fillna(False).astype(bool)].copy()
        sensitivity = benchmark_forecasts(score_rows, peak_quantile=args.peak_quantile)
        sensitivity_gate = promotion_gate(sensitivity)
        sensitivity.to_csv(output / "headline_benchmark_excluding_qa_flags.csv", index=False)

    rolling_benchmark, folds = rolling_origin_evaluation(
        df,
        evaluation_start=args.test_start,
        horizon_days=args.horizon_days,
        step_days=args.step_days,
        peak_quantile=args.peak_quantile,
    )
    rolling_benchmark.to_csv(output / "rolling_origin_benchmark.csv", index=False)
    folds.to_csv(output / "rolling_origin_folds.csv", index=False)
    rolling_summary = summarize_rolling_origin(folds)

    summary = {
        "respondent": args.respondent,
        "test_start": str(args.test_start),
        "peak_quantile": args.peak_quantile,
        "horizon_days": args.horizon_days,
        "step_days": args.step_days,
        "headline_gate": headline_gate,
        "model_info": model_info,
        "rolling_origin": rolling_summary,
        "qa_flag_scoring_sensitivity_gate": sensitivity_gate,
        "notes": [
            "Headline and rolling-origin comparisons score EIA, weekly naive, and ML on common rows.",
            "QA-flagged observations remain in the primary benchmark.",
            "The QA sensitivity view excludes flagged holdout rows from scoring only; it does not retrain the model or alter source values.",
            "Rolling-origin results are reported transparently; no new automatic durable-win rule is imposed beyond the existing EIA minimum gate.",
        ],
    }
    cleaned = {key: _jsonable(value) for key, value in summary.items()}
    (output / "model_evaluation_summary.json").write_text(
        json.dumps(cleaned, indent=2, default=_jsonable) + "\n",
        encoding="utf-8",
    )

    print("GridPulse model evaluation complete.")
    print(f"Headline benchmark: {output / 'headline_benchmark.csv'}")
    print(f"Rolling folds:      {output / 'rolling_origin_folds.csv'}")
    print(f"Summary:            {output / 'model_evaluation_summary.json'}")
    print(json.dumps(cleaned, indent=2, default=_jsonable))


if __name__ == "__main__":
    main()
