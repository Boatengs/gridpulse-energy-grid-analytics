# GridPulse verified PJM results

These compact outputs are generated from the frozen eight-file EIA-930 BALANCE snapshot documented in `DATASET_MANIFEST.md`. The source CSVs themselves are intentionally not committed.

Before evaluation, each downloaded EIA file was checked byte-for-byte against the manifest SHA-256 values. The verification record is in `source_verification.json`.

## 2025 headline benchmark

All three forecasts are scored on the same 8,690 valid holdout hours. Peak hours use one shared top-decile demand threshold of 119,360.1 MW.

| Forecast | MAE (MW) | RMSE (MW) | sMAPE | Peak MAE (MW) |
|---|---:|---:|---:|---:|
| EIA day-ahead | 3,302.6 | 4,148.3 | 3.49% | 4,330.5 |
| Same hour last week | 8,455.1 | 11,616.9 | 8.43% | 14,342.2 |
| GridPulse ML-corrected EIA | **1,842.7** | **2,442.2** | **1.89%** | **2,770.4** |

Against the actual EIA-reported day-ahead forecast, the GridPulse candidate reduces:

- overall MAE by **44.2%**,
- top-decile-demand MAE by **36.0%**.

This clears the project's minimum EIA promotion gate on the 2025 holdout.

## Rolling-origin validation

The expanding-window 30-day evaluation produces 13 valid future folds across 2025. The GridPulse candidate beats EIA on both overall MAE and peak-demand MAE in **13 of 13 folds**.

- median overall improvement: **43.7%**,
- median peak improvement: **25.3%**,
- worst-fold overall improvement: **26.9%**,
- worst-fold peak improvement: **15.1%**.

The detailed fold table is committed as `rolling_origin_folds.csv`.

## 2025 error-slice intelligence

`error_slices/` decomposes the same 8,690 common holdout rows by PJM local hour, month, season, weekday/weekend, and demand decile. Every table reports EIA MAE, GridPulse ML MAE, relative MAE improvement, signed bias, and underforecast rate.

The main findings are deliberately not presented as uniformly positive:

- **23 of 24 local-hour slices beat EIA.** The exception is **08:00 PJM local**, where EIA MAE is 1,668 MW and GridPulse ML MAE is 1,682 MW, a **0.8% regression**.
- The strongest hourly gain is **01:00 PJM local**, where MAE falls from 5,063 MW to 1,380 MW, a **72.7% improvement**.
- Every monthly slice improves. **July** is strongest at **55.2%**; **January** is weakest but still improves **26.5%**.
- **JJA** improves **52.0%**, while **DJF** improves **28.8%**.
- Weekday and weekend slices both improve materially: **45.3%** and **41.1%**, respectively.
- Every demand decile improves on MAE. **D2** is strongest at **55.6%**; the highest-demand decile **D10** is weakest at **36.0%**.

### Peak-demand asymmetry

The D10 result deserves separate treatment. GridPulse reduces peak-decile MAE from **4,330 MW to 2,770 MW**, and mean positive forecast bias falls from roughly **2,149 MW to 1,451 MW**. However, the share of D10 hours in which actual demand exceeds the forecast increases from **63.3% for EIA to 69.2% for GridPulse ML**.

That means the corrected forecast makes peak-hour misses substantially smaller on average, but its residual peak misses are somewhat more frequently on the low side. This is an important operational limitation and a reason not to summarize the model solely with MAE.

The source tables are:

- `error_slices/hour.csv`
- `error_slices/month.csv`
- `error_slices/season.csv`
- `error_slices/day_type.csv`
- `error_slices/demand_decile.csv`
- `error_slices/summary.json`

They are generated reproducibly by `scripts/generate_error_slices.py` from the prepared frozen PJM hourly table.

## QA boundary

The frozen dataset contains one row flagged by the project's source-anomaly rule: PJM demand at 2024-11-21 12:00 local time falls to 56,260 MW between adjacent values near 95,000 MW while reported net generation remains near 98,000 MW. That observation is retained unchanged and flagged rather than smoothed or deleted.

Because that event is in 2024 rather than the 2025 headline holdout, excluding QA-flagged holdout rows from scoring does not change the 2025 gate result.

## Interpretation boundary

These results support a strong but bounded claim: on the frozen PJM 2022–2025 EIA-930 snapshot and the documented feature/timing rules, the residual-correction candidate materially improves on EIA's reported day-ahead forecast overall, during top-decile demand hours, and across all 13 rolling-origin folds.

The slice analysis makes that claim more precise rather than stronger than the evidence allows. The model is **not superior in every local-hour slice**: 08:00 is a small regression, and peak underforecast frequency remains an explicit weakness despite lower peak MAE.

The evidence does **not** establish superiority for other balancing authorities, other years, revised future source snapshots, or a production forecasting system with different information availability. GridPulse also does not predict blackouts.
