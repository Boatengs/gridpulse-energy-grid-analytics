"""Prepare downloaded EIA-930 files for GridPulse.

Recommended:
    python scripts/prepare_downloaded_eia.py \
        --balance-source data/raw/eia930 \
        --respondent PJM \
        --output-dir data/processed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gridpulse.balance import load_balance_exports
from gridpulse.features import add_operational_features
from gridpulse.io import hourly_qa_summary, save_processed
from gridpulse.stress import add_stress_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--balance-source",
        required=True,
        help="CSV file or directory containing EIA930_BALANCE_*.csv files.",
    )
    parser.add_argument(
        "--respondent",
        default="PJM",
        help="Balancing-authority code to keep before concatenating the large files.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for normalized Parquet tables and QA summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hourly, fuel = load_balance_exports(args.balance_source, respondent=args.respondent)
    hourly = add_stress_score(add_operational_features(hourly))

    hourly_path, fuel_path = save_processed(hourly, args.output_dir, fuel)
    qa = hourly_qa_summary(hourly)

    qa_path = Path(args.output_dir) / "qa_summary.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")

    print("GridPulse downloaded-data preparation complete.")
    print(json.dumps(qa, indent=2))
    print(f"Hourly table: {hourly_path}")
    print(f"Fuel table:   {fuel_path}")
    print(f"QA summary:   {qa_path}")


if __name__ == "__main__":
    main()
