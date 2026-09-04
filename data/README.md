# GridPulse data folders

GridPulse now treats a frozen downloaded EIA-930 dataset as the recommended production input.

## Recommended raw layout

```text
data/raw/eia930/
├── region/
│   ├── pjm_2022_h1.csv
│   ├── pjm_2022_h2.csv
│   └── ...
└── fuel/
    ├── pjm_fuel_2022_h1.csv
    ├── pjm_fuel_2022_h2.csv
    └── ...
```

The filenames do not matter. The preparation script reads every CSV in the supplied directory, so EIA download chunks can be kept as separate source files.

## Prepare the analytical layer

```bash
python scripts/prepare_downloaded_eia.py \
  --region-source data/raw/eia930/region \
  --fuel-source data/raw/eia930/fuel \
  --output-dir data/processed
```

Outputs:

- `data/processed/gridpulse_hourly.parquet`
- `data/processed/gridpulse_fuel_mix.parquet`
- `data/processed/qa_summary.json`

Raw and processed data files are intentionally ignored by Git. The repository stores code, tests, documentation, and code-derived figures rather than republishing large EIA exports.
