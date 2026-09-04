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

## Source-data QA anomalies

GridPulse flags suspicious source events without changing the underlying EIA values. The current row-level rules mark:

- an isolated one-hour demand discontinuity when a large step is immediately reversed in the following hour, or
- a large exact-hour demand step that coincides with a large balance residual.

The default thresholds are a 25% demand step and a 10,000 MW absolute balance residual. These are project QA heuristics, not EIA correction rules.

The November 21, 2024 PJM demand sequence around noon local time is the motivating example: the reported demand falls from roughly 94.8 GW to 56.3 GW and then returns to roughly 95.5 GW while net generation remains near 98 GW. GridPulse retains those reported values and flags the discontinuity for investigation rather than smoothing or deleting it.

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

Three forecasts can now be scored on one common future holdout row set:

- EIA-reported day-ahead demand forecast,
- same UTC hour one week earlier,
- GridPulse's first ML candidate: a gradient-boosted residual correction to the EIA forecast.

Metrics:

- MAE,
- RMSE,
- sMAPE,
- peak-hour MAE for the top 10% of holdout demand hours.

The peak threshold is shared across models, and all headline metrics use identical rows so a model cannot benefit from being scored on an easier subset.

The weekly-naive forecast remains useful context, but it is **not** the portfolio promotion bar. The minimum model gate requires the ML candidate to beat the EIA-reported day-ahead forecast on both overall MAE and peak-hour MAE. Passing that gate is necessary, not sufficient; rolling-origin stability and error-slice review are still required before claiming a durable improvement.

## First ML candidate

The initial candidate predicts the residual error in EIA's reported day-ahead forecast with `HistGradientBoostingRegressor` and then adds that correction back to `forecast_mw`.

To keep the timing conservative, observed-demand and prior-error features are exact-time lags of at least 48 hours. The current feature set includes:

- EIA-reported `forecast_mw` for the target hour,
- cyclical hour-of-day, day-of-week, and month terms,
- exact demand lags at 48, 168, and 336 hours,
- exact EIA forecast-error lags at 48 and 168 hours.

No contemporaneous generation, interchange, or target-hour actual-demand information is supplied to the model.

QA-flagged source observations remain in the primary benchmark. Any later sensitivity analysis that excludes them must be clearly labeled as a secondary view rather than silently replacing the headline result.

## Modeling roadmap

1. same-hour-last-week diagnostic baseline,
2. EIA-reported day-ahead operational benchmark,
3. gradient-boosted EIA residual-correction candidate,
4. rolling-origin validation,
5. peak-hour / hour-of-day / seasonal error slices,
6. QA-anomaly sensitivity review,
7. SHAP only if the tree model earns its added complexity.

Random train/test splits are not appropriate for this time-series problem.
