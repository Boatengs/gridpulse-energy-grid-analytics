# Data handling

`data/raw/` is reserved for source extracts and `data/processed/` for normalized hourly analytical tables. Real EIA pulls are intentionally gitignored; public GitHub should contain code, schemas, compact evidence, and reproducible instructions rather than large rotating API extracts.

The dashboard falls back to a deterministic synthetic development fixture only when `data/processed/hourly_grid.csv` does not exist. That fixture must never be described as an EIA result.
