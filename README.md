# GridPulse — Energy Demand & Grid Stress Analytics

**Hourly demand → forecast error → ramping → generation mix → interchange → stress screening → forecasting → operational dashboard**

GridPulse is a visual-first energy analytics project built around U.S. Energy Information Administration Form EIA-930 hourly grid data. The central question is:

> **When does electricity demand become unusually difficult to forecast or serve, what operating conditions coincide with those hours, and how can those conditions be surfaced for review?**

The project is intentionally broader than a forecasting notebook. It combines reproducible data engineering, time-series diagnostics, forecast-performance analysis, transparent stress screening, generation-mix context, and a dashboard designed to make operating patterns inspectable.

> **Current phase:** downloaded EIA data is now the recommended production path. The API client remains available as an optional route, while the dashboard defaults to a frozen local analytical dataset for reproducibility.

## Visual proof — development pipeline

![Synthetic development demand versus forecast](figures/demo_demand_forecast.svg)

**What this shows:** the first GridPulse visual layer overlays actual demand and the day-ahead forecast so forecast misses can be read in the same temporal context as demand peaks and ramps. This committed snapshot uses the synthetic development fixture only and will be replaced with a genuine EIA-result figure after the downloaded dataset is processed.

![Synthetic development stress timeline](figures/demo_stress_timeline.svg)

**What this shows:** the operational-stress view combines four inspectable components—demand level, absolute forecast error, ramping, and interchange dependence. The score is a screening device, not an official EIA/NERC reliability rating and not a blackout prediction.

## Recommended EIA download

Start with **PJM** and use a multi-year window:

- **Balancing authority:** PJM
- **Period:** January 1, 2022 through December 31, 2025
- **Format:** CSV
- **Dataset 1:** hourly demand, day-ahead demand forecast, net generation, and total interchange
- **Dataset 2:** hourly net generation by energy source

Keeping the four-year window gives GridPulse enough history for seasonality, rolling validation, stress-event analysis, and a clean 2025 out-of-time evaluation.

If EIA provides the export in several date chunks, keep every CSV in the relevant raw-data folder. The preparation script combines them automatically.

## Data workflow

```text
Downloaded EIA-930 CSV export(s)
        ↓
raw files preserved unchanged
        ↓
schema validation + UTC normalization
        ↓
D / DF / NG / TI pivot to one hourly table
        ↓
fuel-generation normalization
        ↓
missing-hour / duplicate / missing-value QA
        ↓
operational feature engineering
        ↓
transparent stress screening
        ↓
Parquet analytical layer
        ↓
dashboard + forecasting + model validation
```

The local-data path is designed to make every model and figure reproducible from the same source snapshot.

## Prepare downloaded data

Recommended folder layout:

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

Then run:

```bash
python scripts/prepare_downloaded_eia.py \
  --region-source data/raw/eia930/region \
  --fuel-source data/raw/eia930/fuel \
  --output-dir data/processed
```

The script creates:

```text
data/processed/gridpulse_hourly.parquet
data/processed/gridpulse_fuel_mix.parquet
data/processed/qa_summary.json
```

The dashboard reads those Parquet files directly. No API key is required.

## Dashboard surfaces

GridPulse now supports the following analytical views:

1. **Demand vs day-ahead forecast** — hourly operating overlay.
2. **Forecast-error distribution** — signed under- vs over-forecasting.
3. **Demand ramp timeline** — separates rapid changes from absolute load level.
4. **Demand heatmap** — date × hour structure for recurring load shape and unusual days.
5. **Operational-stress timeline** — transparent 0–100 screening signal.
6. **Net generation + interchange** — supply context around high-demand periods.
7. **Highest-stress event table** — turns the composite score back into inspectable evidence.
8. **Generation mix by energy source** — stacked hourly generation once the companion EIA export is present.
9. **Renewable generation share** — descriptive generation-portfolio context.
10. **Forecasting baseline panel** — same-hour-last-week out-of-time benchmark.
11. **KPI strip** — peak demand, forecast MAE, maximum hourly ramp, and maximum stress signal.
12. **Data-QA sidebar** — missing hours, duplicate respondent-hours, missing demand, and non-positive demand checks.

Every major dashboard output includes a short plain-language interpretation.

## Stress screening

The initial screening score remains deliberately simple and inspectable:

```text
40% demand percentile
25% absolute forecast-error percentile
20% normalized absolute hourly demand ramp
15% interchange-dependence percentile
```

These weights are **provisional analytical assumptions**. They help prioritize unusual combinations of operating signals for review. They are not official reliability standards.

## Forecasting baseline

The first benchmark is intentionally difficult to overstate:

> **Predict each hour using demand from the same hour one week earlier.**

The baseline is evaluated on a future holdout period with:

- MAE
- RMSE
- sMAPE
- peak-hour MAE

A more complex model only earns a place if it beats this baseline out of time, especially during high-demand hours.

Planned next model:

- calendar and lag features
- rolling demand features
- gradient-boosted trees
- rolling-origin validation
- SHAP explanations if the tree model materially improves performance

## Optional API route

`src/gridpulse/eia.py` remains in the project. The dashboard can still query EIA API v2 when an `EIA_API_KEY` is configured, which is useful for recent-data checks or experiments.

The API is no longer required for the main project workflow.

## Documentation standard

GridPulse follows the portfolio-wide standard:

**Markdown context → humanly commented code → output → Markdown interpretation → limitations / decision relevance.**

README visuals will be replaced with genuine code-derived EIA figures once the downloaded PJM dataset is processed.

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
├── src/gridpulse/
│   ├── eia.py
│   ├── io.py
│   ├── features.py
│   ├── forecasting.py
│   ├── stress.py
│   └── demo.py
├── scripts/
│   ├── prepare_downloaded_eia.py
│   ├── fetch_eia.py
│   └── generate_readme_figures.py
├── notebooks/
│   └── 01_gridpulse_walkthrough.ipynb
├── tests/
├── data/
├── figures/
└── .github/workflows/ci.yml
```

## Guardrails

- GridPulse does **not** predict blackouts.
- Stress flags describe unusual combinations of observed operating signals and require interpretation.
- EIA-930 values are operational data and can contain missing or revised observations.
- Forecast comparisons preserve time order; random train/test splits are not appropriate.
- More complex models are retained only when they improve future-period performance meaningfully.
- Raw downloaded data is not republished in Git; the repository stores the reproducible code and analytical evidence.
