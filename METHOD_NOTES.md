# GridPulse Method Notes

## Source

The current production snapshot uses eight official EIA-930 six-month BALANCE CSV files covering PJM from 2022 through 2025 local time. Exact filenames and SHA-256 hashes are recorded in `DATASET_MANIFEST.md`.

## Why the downloaded path is primary

A frozen source snapshot makes model comparisons, README evidence, and reviewer reproduction stable even if preliminary EIA observations are revised later. The live API client remains available for recent-data checks.

## Ingestion

`gridpulse.balance.load_balance_exports()`:

1. reads large all-balancing-authority files in chunks,
2. filters to the requested BA before concatenation,
3. prefers EIA adjusted values for demand/generation/interchange,
4. preserves imputation flags,
5. normalizes the 2024 H2 fuel-schema change,
6. returns one hourly operating table and one long fuel table.

## Units

The six-month BALANCE exports label operating values in MW. GridPulse uses `_mw` fields and MW dashboard labels.

## Forecast error

```text
forecast_error_mw = demand_mw - forecast_mw
```

Positive values mean actual demand exceeded the reported day-ahead forecast.

## Demand ramp

```text
demand_ramp_pct = (demand_t / demand_t-1 - 1) × 100
```

Ramps are kept as observed. Extreme values are inspected against QA evidence before they are interpreted operationally.

## Balance residual

```text
balance_residual_mw =
    net_generation_mw - demand_mw - total_interchange_mw
```

This is a diagnostic rather than an automatic correction rule. Large deviations can reflect source/reporting issues or accounting differences that deserve inspection.

## Stress screening

Current provisional weights:

```text
40% demand percentile
25% absolute forecast-error percentile
20% normalized absolute demand ramp
15% interchange-dependence percentile
```

If an EIA component is missing, GridPulse reweights over available components rather than filling the missing component with zero. The score is not an official reliability or emergency metric.

## Forecast validation

Two 2025 benchmarks are currently reported:

- EIA-reported day-ahead demand forecast
- same UTC hour one week earlier

Metrics:

- MAE
- RMSE
- sMAPE
- peak-hour MAE for the top 10% of holdout demand hours

The EIA forecast is an operational benchmark reported by the source, not a model trained by GridPulse.

## Modeling roadmap

1. same-hour-last-week baseline
2. calendar + lag linear baseline
3. gradient-boosted trees
4. rolling-origin validation
5. peak-hour / hour-of-day / seasonal error slices
6. SHAP only if the tree model earns its added complexity

Random train/test splits are not appropriate for this time-series problem.
