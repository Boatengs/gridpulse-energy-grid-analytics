# GridPulse — Energy Demand & Grid Stress Analytics

**Hourly demand → forecast error → ramping → generation mix → interchange → QA review → stress screening → forecasting → operational dashboard**

GridPulse is a visual-first energy analytics project built around U.S. Energy Information Administration Form EIA-930 hourly grid data. The central question is:

> **When does electricity demand become unusually difficult to forecast or serve, what operating conditions coincide with those hours, and can a model improve on the actual EIA-reported day-ahead forecast?**

The project combines reproducible data engineering, time-series diagnostics, source-data QA, operational stress screening, generation-mix context, forecast benchmarking, rolling-origin validation, and a Streamlit dashboard.

## Verified result

GridPulse now has a real out-of-time PJM result from the frozen 2022–2025 EIA-930 snapshot.

All headline forecasts are scored on the same **8,690 valid 2025 holdout hours**. Peak performance uses one shared top-decile demand threshold of **119,360.1 MW**.

| Forecast | MAE (MW) | RMSE (MW) | sMAPE | Peak MAE (MW) |
|---|---:|---:|---:|---:|
| EIA day-ahead | 3,302.6 | 4,148.3 | 3.49% | 4,330.5 |
| Same hour last week | 8,455.1 | 11,616.9 | 8.43% | 14,342.2 |
| **GridPulse ML-corrected EIA** | **1,842.7** | **2,442.2** | **1.89%** | **2,770.4** |

Against EIA's actual reported day-ahead forecast, the GridPulse candidate reduces:

- **overall MAE by 44.2%**, and
- **peak-demand MAE by 36.0%**.

That is not just a single-split result. Expanding-window 30-day rolling-origin validation produced **13 valid future folds**, and the GridPulse candidate beat EIA on both overall and peak-demand MAE in **13 of 13 folds**.

- median overall improvement: **43.7%**,
- median peak improvement: **25.3%**,
- worst-fold overall improvement: **26.9%**,
- worst-fold peak improvement: **15.1%**.

The exact machine-readable outputs are committed under [`results/`](results/README.md).

## Real PJM evidence

![PJM demand versus EIA and GridPulse forecasts around the 2025 annual peak](figures/pjm_2025_peak_demand_forecast.svg)

The annual-peak view compares actual PJM demand directly with EIA's reported day-ahead forecast and the GridPulse residual-correction candidate. The ML candidate is not a replacement weather/load-forecast stack; it learns a correction to EIA's forecast using only conservatively timed historical features.

![2025 PJM forecast benchmark](figures/pjm_2025_forecast_benchmark.svg)

The benchmark uses identical scoring rows and one shared peak-demand threshold. The weekly-naive model remains useful diagnostic context, but it is deliberately **not** the promotion bar; the meaningful comparison is GridPulse versus EIA.

![PJM reported generation mix in June 2025](figures/pjm_2025_june_generation_mix.svg)

Generation mix provides operating context around the summer-demand period rather than being used as contemporaneous target-hour information in the forecasting model.

The older `demo_*.svg` files remain in `figures/` as clearly labeled synthetic development fixtures, not portfolio evidence.

## Source snapshot

The production snapshot uses **eight official EIA-930 six-month BALANCE CSV files** covering PJM from 2022 through 2025 local time. Exact filenames and SHA-256 hashes are recorded in `DATASET_MANIFEST.md`.

For the verified result above, the files were re-fetched from EIA's official six-month archive and every SHA-256 matched the frozen manifest before preparation or modeling. The compact verification record is committed at `results/source_verification.json`.

The ingestion path:

- reads the large all-balancing-authority files in chunks,
- filters to PJM before concatenation,
- normalizes the mid-2024 schema change,
- prefers adjusted demand/generation/interchange values when available,
- preserves imputation flags,
- standardizes operating values on **MW** fields such as `demand_mw`, `forecast_mw`, and `net_generation_mw`.

The prepared PJM table contains **35,064 hourly rows**, with no duplicate UTC timestamps and no missing hourly slots across the frozen coverage window.

## Data workflow

```text
Eight frozen EIA-930 BALANCE CSV files
        ↓
SHA-256 snapshot verification
        ↓
PJM filtering before concatenation
        ↓
2024 schema normalization + MW standardization
        ↓
hourly operating table + long generation-mix table
        ↓
missing-hour / duplicate / missing-value QA
        ↓
non-mutating source-anomaly flags
        ↓
operational feature engineering
        ↓
transparent stress screening
        ↓
Parquet analytical layer
        ↓
EIA benchmark + ML candidate + rolling-origin validation
        ↓
dashboard + committed analytical evidence
```

## Prepare downloaded data

Keep the eight BALANCE files under a local raw-data folder, for example:

```text
data/raw/eia930/
├── EIA930_BALANCE_2022_Jan_Jun.csv
├── EIA930_BALANCE_2022_Jul_Dec.csv
├── ...
└── EIA930_BALANCE_2025_Jul_Dec.csv
```

Then run:

```bash
python scripts/prepare_downloaded_eia.py \
  --balance-source data/raw/eia930 \
  --respondent PJM \
  --output-dir data/processed
```

The script creates:

```text
data/processed/gridpulse_hourly.parquet
data/processed/gridpulse_fuel_mix.parquet
data/processed/qa_summary.json
```

Raw source files and processed Parquet tables are intentionally not republished in Git.

## Source-data QA policy

GridPulse treats suspicious source observations as evidence to investigate, not values to quietly erase.

The current row-level rules flag:

- an isolated one-hour demand discontinuity when a large step is immediately reversed in the following hour, or
- a large exact-hour demand step that coincides with a large generation-demand-interchange balance residual.

The default QA thresholds are a **25% demand step** and a **10,000 MW absolute balance residual**. These are project heuristics, not EIA correction rules.

The frozen snapshot contains one combined QA anomaly: **November 21, 2024 at 12:00 PM PJM local time**. Reported demand falls from **94,812 MW to 56,260 MW and then returns to 95,482 MW**, while reported net generation remains near **98,000 MW**. GridPulse retains the observation and flags it rather than smoothing, clipping, interpolating, or deleting it.

## Stress screening

The initial screening score is deliberately simple and inspectable:

```text
40% demand percentile
25% absolute forecast-error percentile
20% normalized absolute hourly demand ramp
15% interchange-dependence percentile
```

If a component is missing, GridPulse reweights over available components rather than treating the missing value as zero.

The stress score is a screening device. It is **not** an official EIA/NERC reliability rating and **not** a blackout probability.

## Forecasting standard

The weekly-naive forecast predicts each hour using demand from the same exact UTC hour one week earlier. It is retained because a simple baseline is useful, but beating it is not considered a portfolio win.

GridPulse compares three forecasts on common future rows:

- **EIA-reported day-ahead forecast** — the operational source benchmark,
- **same hour last week** — the diagnostic baseline,
- **ML-corrected EIA** — the GridPulse candidate.

Headline metrics are MAE, RMSE, sMAPE, and top-decile-demand MAE.

### Minimum promotion gate

A candidate must beat EIA on both:

1. overall holdout MAE, and
2. peak-hour MAE.

The current candidate passes both conditions on the 2025 headline holdout and on every valid rolling-origin fold in the current evaluation.

## First ML candidate

The first candidate is intentionally narrow: a gradient-boosted residual correction to the reported EIA day-ahead forecast.

It predicts:

```text
actual demand − EIA forecast
```

and adds the predicted residual back to `forecast_mw`.

The feature set contains:

- target-hour EIA `forecast_mw`,
- cyclical hour-of-day, day-of-week, and month terms,
- exact demand lags at 48, 168, and 336 hours,
- exact EIA forecast-error lags at 48 and 168 hours.

Observed-demand and prior-error features are lagged by **at least 48 hours**. No contemporaneous target-hour demand, generation, or interchange values are supplied to the model.

## Rolling-origin validation

`scripts/evaluate_models.py` runs the headline 2025 benchmark and expanding-window future folds. The default project evaluation uses 30-day horizons stepped forward 30 days at a time.

For each fold:

- training history ends before the fold begins,
- EIA, weekly naive, and ML are scored on identical valid rows,
- one common peak-demand threshold is used within the fold,
- the existing EIA promotion gate is recorded transparently.

The committed fold-level evidence is in `results/rolling_origin_folds.csv`.

## Dashboard surfaces

GridPulse supports:

1. demand vs day-ahead forecast,
2. forecast-error distribution,
3. demand ramp timeline,
4. demand heatmap,
5. operational-stress timeline,
6. net generation + interchange,
7. highest-stress event table,
8. source-data QA anomaly table,
9. generation mix by energy source,
10. renewable generation share,
11. EIA vs weekly naive vs ML out-of-time benchmark,
12. peak-demand forecast benchmark,
13. model promotion gate,
14. KPI strip,
15. data-QA sidebar.

Every major dashboard output includes a short plain-language interpretation.

## Current interpretation

The current evidence supports a strong but bounded statement:

> On the frozen PJM 2022–2025 EIA-930 snapshot, using the documented feature timing and 2025 out-of-time evaluation, the GridPulse residual-correction candidate materially improves on EIA's reported day-ahead forecast and that improvement is stable across the project's rolling-origin folds.

It does **not** establish superiority for other balancing authorities, other years, revised future source snapshots, or a production forecasting stack with different information availability.

## Next analytical extensions

- hour-of-day, season, weekday/weekend, and demand-decile error slices,
- broader balancing-authority replication,
- tighter feature-availability audits against an explicit forecast-issuance clock if available,
- SHAP only if explanation work is useful after the model has already earned its complexity.

Random train/test splits are not appropriate for this time-series problem.

## Optional API route

`src/gridpulse/eia.py` remains in the project. The dashboard can query EIA API v2 when an `EIA_API_KEY` is configured for recent-data checks or experiments. The API is not required for the main frozen-snapshot workflow.

## Quick start

```bash
git clone https://github.com/Boatengs/gridpulse-energy-grid-analytics.git
cd gridpulse-energy-grid-analytics
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
streamlit run app.py
```

## Repository structure

```text
.
├── app.py
├── README.md
├── PROJECT_CHARTER.md
├── METHOD_NOTES.md
├── DATA_DICTIONARY.md
├── DATASET_MANIFEST.md
├── results/
│   ├── README.md
│   ├── headline_benchmark.csv
│   ├── model_evaluation_summary.json
│   ├── rolling_origin_folds.csv
│   └── source_verification.json
├── src/gridpulse/
│   ├── balance.py
│   ├── eia.py
│   ├── io.py
│   ├── features.py
│   ├── forecasting.py
│   ├── validation.py
│   ├── stress.py
│   └── demo.py
├── scripts/
│   ├── prepare_downloaded_eia.py
│   ├── evaluate_models.py
│   ├── fetch_eia.py
│   └── generate_readme_figures.py
├── notebooks/
├── tests/
├── data/
├── figures/
└── .github/workflows/ci.yml
```

## Guardrails

- GridPulse does **not** predict blackouts.
- Stress flags describe unusual combinations of observed operating signals and require interpretation.
- QA flags do not silently mutate or delete EIA observations.
- EIA-930 values can contain missing, imputed, anomalous, or revised observations.
- Forecast comparisons preserve chronological order.
- Forecasts are compared on common rows and a shared peak-demand definition.
- Beating the weekly-naive baseline alone is not considered a model win.
- Raw downloaded data is not republished in Git; the repository stores reproducible code, source hashes, compact result tables, and analytical figures.
