# GridPulse Method Notes

## Source

The current production snapshot uses eight official EIA-930 six-month BALANCE CSV files covering PJM from 2022 through 2025 local time. Exact filenames and SHA-256 hashes are recorded in `DATASET_MANIFEST.md`.

The real-data evaluation reproduced those eight files from EIA's official six-month archive and verified every file against the manifest hash before preparation or modeling. The compact verification record is committed under `results/source_verification.json`.

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

The prepared frozen snapshot contains one row meeting the combined anomaly rule: 2024-11-21 12:00 PJM local time, with demand 56,260 MW, day-ahead forecast 89,661 MW, net generation 98,308 MW, and total interchange 2,152 MW.

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

Three forecasts are scored on common future rows:

- EIA-reported day-ahead demand forecast,
- same UTC hour one week earlier,
- GridPulse's first ML candidate: a gradient-boosted residual correction to the EIA forecast.

Metrics:

- MAE,
- RMSE,
- sMAPE,
- peak-hour MAE for the top 10% of holdout demand hours.

The peak threshold is shared across models, and all headline metrics use identical rows so a model cannot benefit from being scored on an easier subset.

The weekly-naive forecast remains useful context, but it is **not** the portfolio promotion bar. The minimum model gate requires the ML candidate to beat the EIA-reported day-ahead forecast on both overall MAE and peak-hour MAE.

## First ML candidate

The initial candidate predicts the residual error in EIA's reported day-ahead forecast with `HistGradientBoostingRegressor` and then adds that correction back to `forecast_mw`.

To keep the timing conservative, observed-demand and prior-error features are exact-time lags of at least 48 hours. The current feature set includes:

- EIA-reported `forecast_mw` for the target hour,
- cyclical hour-of-day, day-of-week, and month terms,
- exact demand lags at 48, 168, and 336 hours,
- exact EIA forecast-error lags at 48 and 168 hours.

No contemporaneous generation, interchange, or target-hour actual-demand information is supplied to the model.

QA-flagged source observations remain in the primary benchmark. Any sensitivity analysis that excludes them is explicitly labeled as a secondary scoring view.

## Verified 2025 result

The frozen PJM evaluation uses 2025 as the future holdout. On the 8,690 common rows where EIA, weekly naive, and the ML candidate can all be scored, the shared top-decile demand threshold is 119,360.1 MW.

| Forecast | MAE (MW) | RMSE (MW) | sMAPE | Peak MAE (MW) |
|---|---:|---:|---:|---:|
| EIA day-ahead | 3,302.6 | 4,148.3 | 3.49% | 4,330.5 |
| Same hour last week | 8,455.1 | 11,616.9 | 8.43% | 14,342.2 |
| ML-corrected EIA | **1,842.7** | **2,442.2** | **1.89%** | **2,770.4** |

Relative to EIA, the candidate reduces overall MAE by **44.2%** and peak-hour MAE by **36.0%**. That clears the minimum EIA promotion gate.

## Rolling-origin stability

A single holdout win is not treated as sufficient evidence. GridPulse also runs expanding-window 30-day future folds across 2025.

The current run produced **13 valid folds**, and the ML candidate beat EIA on both overall MAE and peak-hour MAE in **13 of 13**.

- median overall improvement: **43.7%**,
- median peak improvement: **25.3%**,
- worst-fold overall improvement: **26.9%**,
- worst-fold peak improvement: **15.1%**.

The exact headline and fold tables are committed under `results/`.

This supports a durable improvement claim **within this defined PJM experiment**. It does not establish performance for other balancing authorities, other years, revised source snapshots, or a production system with different feature availability.

## Modeling roadmap

Completed for the current candidate:

1. EIA-reported day-ahead operational benchmark,
2. weekly-naive diagnostic baseline,
3. gradient-boosted EIA residual-correction candidate,
4. rolling-origin validation,
5. QA-anomaly scoring sensitivity.

Useful next analytical extensions:

1. hour-of-day, season, weekday/weekend, and demand-decile error slices,
2. calibration of feature timing against a more explicit forecast-issuance clock if available,
3. broader balancing-authority replication,
4. SHAP only if explanation work is useful after the model has already earned its complexity.

Random train/test splits are not appropriate for this time-series problem.
