"""Prepare downloaded EIA-930 CSV files for GridPulse.

Example:
    python scripts/prepare_downloaded_eia.py \
        --region-source data/raw/eia930/region \
        --fuel-source data/raw/eia930/fuel \
        --output-dir data/processed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gridpulse.features import add_operational_features
from gridpulse.io import (
    hourly_qa_summary,
    load_fuel_exports,
    load_region_exports,
    save_processed,
)
from gridpulse.stress import add_stress_score


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--region-source",
        required=True,
        help="CSV file or directory containing downloaded EIA region-data exports.",
    )
    parser.add_argument(
        "--fuel-source",
        help="Optional CSV file or directory containing EIA fuel-type exports.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        help="Directory for the normalized Parquet tables.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    region = load_region_exports(args.region_source)
    region = add_stress_score(add_operational_features(region))

    fuel = None
    if args.fuel_source:
        fuel = load_fuel_exports(args.fuel_source)

    hourly_path, fuel_path = save_processed(region, args.output_dir, fuel)
    qa = hourly_qa_summary(region)

    print("GridPulse downloaded-data preparation complete.")
    print(json.dumps(qa, indent=2))
    print(f"Hourly table: {hourly_path}")
    if fuel_path:
        print(f"Fuel table:   {fuel_path}")

    qa_path = Path(args.output_dir) / "qa_summary.json"
    qa_path.write_text(json.dumps(qa, indent=2) + "\n", encoding="utf-8")
    print(f"QA summary:   {qa_path}")


if __name__ == "__main__":
    main()
