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

## QA boundary

The frozen dataset contains one row flagged by the project's source-anomaly rule: PJM demand at 2024-11-21 12:00 local time falls to 56,260 MW between adjacent values near 95,000 MW while reported net generation remains near 98,000 MW. That observation is retained unchanged and flagged rather than smoothed or deleted.

Because that event is in 2024 rather than the 2025 headline holdout, excluding QA-flagged holdout rows from scoring does not change the 2025 gate result.

## Interpretation boundary

These results support a strong claim for this defined experiment: on the frozen PJM 2022–2025 EIA-930 snapshot and the documented feature/timing rules, the residual-correction candidate materially improves on EIA's reported day-ahead forecast and does so consistently across the 2025 rolling folds.

They do **not** establish superiority for other balancing authorities, other years, revised future source snapshots, or a production forecasting system with different information availability. GridPulse also does not predict blackouts.
