# GridPulse model evaluation

GridPulse does not treat one favorable train/test split as enough evidence for a forecasting claim.

The production evaluation now has two layers:

1. a fixed 2025 holdout benchmark, and
2. expanding-window rolling-origin folds across the same future period.

In every comparison, the EIA-reported day-ahead forecast, same-hour-last-week baseline, and GridPulse ML candidate are scored on identical rows with one shared peak-demand threshold.

## Run the evaluation

After preparing the existing eight EIA-930 BALANCE files:

```bash
python scripts/evaluate_models.py \
  --hourly-path data/processed/gridpulse_hourly.parquet \
  --respondent PJM \
  --test-start 2025-01-01 \
  --horizon-days 30 \
  --step-days 30 \
  --output-dir data/processed/model_evaluation
```

No new source download is required.

## Outputs

The command writes:

```text
data/processed/model_evaluation/
├── headline_benchmark.csv
├── headline_benchmark_excluding_qa_flags.csv   # when QA flags exist
├── rolling_origin_benchmark.csv
├── rolling_origin_folds.csv
└── model_evaluation_summary.json
```

`headline_benchmark.csv` contains the fixed future-holdout metrics for EIA day-ahead, weekly naive, and ML-corrected EIA.

`rolling_origin_benchmark.csv` contains the same metrics for each expanding-window fold.

`rolling_origin_folds.csv` records whether the ML candidate clears the existing minimum EIA gate in each fold, along with overall and peak-hour improvement percentages.

`model_evaluation_summary.json` reports the number of valid folds, the share that beat EIA on both headline MAE measures, median improvement, and worst-fold improvement.

## Interpretation standard

The existing minimum gate remains unchanged: the ML candidate must beat EIA on both overall MAE and peak-hour MAE.

Rolling-origin validation does **not** introduce an arbitrary new promotion threshold. Instead, it makes stability visible. A portfolio claim should discuss how many folds beat EIA, the median improvement, the worst fold, and whether gains survive peak-demand evaluation.

A model that wins on the single 2025 split but fails repeatedly across rolling folds should not be described as a durable improvement.

## QA sensitivity

QA-flagged observations remain in the primary benchmark.

When `qa_anomaly` is present, the evaluation also writes a secondary scoring sensitivity that excludes flagged holdout rows. This sensitivity does not retrain the model and does not alter, smooth, clip, or delete EIA source values. It exists only to show whether a small number of suspicious source observations materially change the headline comparison.

## Current evidence status

This workflow is implemented in the repository, but the real 2025 result is not stored in Git because the frozen BALANCE source files remain outside the repository. Do not claim that the ML model beats EIA until the command above has been run against the existing local PJM snapshot and the resulting evidence has been reviewed.
