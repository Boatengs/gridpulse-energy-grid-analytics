from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

from gridpulse.eia import EIAClient
from gridpulse.features import add_operational_features
from gridpulse.stress import add_stress_score


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch EIA-930 hourly region data for GridPulse.")
    parser.add_argument("--respondent", default=os.getenv("GRIDPULSE_RESPONDENT", "PJM"))
    parser.add_argument("--start", required=True, help="Example: 2025-01-01T00")
    parser.add_argument("--end", required=True, help="Example: 2025-03-31T23")
    parser.add_argument("--output", type=Path, default=Path("data/processed/hourly_grid.csv"))
    args = parser.parse_args()

    load_dotenv()
    api_key = os.getenv("EIA_API_KEY")
    if not api_key:
        raise SystemExit("EIA_API_KEY is required. Copy .env.example to .env and add your free EIA key.")

    client = EIAClient(api_key)
    raw = client.region_data(args.respondent, args.start, args.end)
    enriched = add_stress_score(add_operational_features(raw))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(args.output, index=False)
    print(f"Saved {len(enriched):,} hourly rows to {args.output}")


if __name__ == "__main__":
    main()
