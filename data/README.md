# Data folders

Raw EIA files and processed analytical tables are intentionally excluded from Git because the source snapshot is large.

## Current source snapshot

The project uses eight official six-month `EIA930_BALANCE` CSV files for PJM covering 2022–2025. Exact filenames and SHA-256 hashes are recorded in `../DATASET_MANIFEST.md`.

Place them under:

```text
data/raw/eia930/
```

Then run:

```bash
python scripts/prepare_downloaded_eia.py \
  --balance-source data/raw/eia930 \
  --respondent PJM \
  --output-dir data/processed
```

Expected outputs:

```text
data/processed/gridpulse_hourly.parquet
data/processed/gridpulse_fuel_mix.parquet
data/processed/qa_summary.json
```

Do not manually edit the raw CSV files. If EIA republishes a revised snapshot, preserve the new files separately and update the manifest hashes before replacing analytical evidence.
