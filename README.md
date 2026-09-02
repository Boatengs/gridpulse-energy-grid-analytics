# GridPulse — Energy Demand & Grid Stress Analytics

**Hourly demand → forecast error → ramping → generation & interchange → stress screening → forecasting → operational dashboard**

GridPulse is a visual-first energy analytics project built around U.S. Energy Information Administration Form EIA-930 hourly grid data. The project asks a practical operations question:

> **When does electricity demand become unusually difficult to forecast or serve, what operating conditions coincide with those hours, and how can those conditions be surfaced for review?**

The project is intentionally broader than a forecasting notebook. It combines reproducible EIA ingestion, data QA, time-series diagnostics, forecast-performance analysis, transparent stress screening, and a dashboard designed to make operating patterns inspectable.

> **Current phase:** Phase 1 foundation. The Streamlit dashboard now queries the EIA API directly into memory and caches the response for one hour. A deterministic synthetic fixture remains only as a clearly labeled fallback when an API key is unavailable or a live request fails. Demo values are never presented as EIA findings.

## Visual proof — Phase 1 dashboard pipeline

![Synthetic development demand versus forecast](figures/demo_demand_forecast.svg)

**What this shows:** the first GridPulse visual layer overlays actual demand and the day-ahead forecast so forecast misses can be read in the same temporal context as demand peaks and ramps. This committed snapshot uses the synthetic development fixture only; the running dashboard queries EIA directly once an API key is configured.

![Synthetic development stress timeline](figures/demo_stress_timeline.svg)

**What this shows:** the operational-stress view combines four inspectable components—demand level, absolute forecast error, ramping, and interchange dependence. The score is a screening device, not an official EIA/NERC reliability rating and not a blackout prediction.

## Dashboard surfaces

The first Streamlit dashboard already supports a visual operations workflow:

1. **Demand vs day-ahead forecast** — hourly overlay with unified hover.
2. **Forecast-error distribution** — signed errors reveal under- vs over-forecasting.
3. **Demand ramp timeline** — isolates rapid changes from simple demand level.
4. **Demand heatmap** — date × hour view for recurring load shape and unusual days.
5. **Operational-stress timeline** — transparent 0–100 screening signal.
6. **Net generation + interchange** — supply context around high-demand hours.
7. **Highest-stress event table** — returns the composite signal to its underlying evidence.
8. **KPI strip** — peak demand, forecast MAE, maximum hourly ramp, maximum stress signal.

The next dashboard layer will add generation-by-fuel stacked areas, renewable share, regional comparisons, rolling forecast validation, and model-error slices.

## Data source

GridPulse uses the EIA API v2 `electricity/rto` family, sourced from Form EIA-930. The primary hourly route contains:

- `D` — demand
- `DF` — day-ahead demand forecast
- `NG` — net generation
- `TI` — total interchange

Generation by energy source will use the companion hourly `fuel-type-data` route.

An individual EIA API key is required. GridPulse reads it from Streamlit secrets or `.env`; the key must never be committed. The normal dashboard path does **not** require a downloaded CSV.

## Analytical workflow

```text
EIA-930 API
    ↓
direct HTTPS query + one-hour Streamlit cache
    ↓
hourly ingestion + UTC normalization
    ↓
QA: duplicates / missing hours / missing values / plausible ranges
    ↓
demand, ramp and forecast-error features
    ↓
generation + interchange context
    ↓
transparent operational-stress screening
    ↓
seasonal-naive baseline
    ↓
rolling time-series model validation
    ↓
visual operations dashboard + README evidence
```

## Stress screening — Phase 1

The initial screening score is deliberately simple and documented:

```text
40% demand percentile
25% absolute forecast-error percentile
20% normalized absolute hourly demand ramp
15% interchange-dependence percentile
```

These weights are **provisional analytical assumptions**. They exist to make multi-signal operating periods easier to inspect and will be sensitivity-tested later. They are not reliability standards.

## Forecasting roadmap

Every forecasting model must beat a simple reference model on a future time window.

Planned comparison:

1. seasonal naive / same-hour-last-week
2. calendar + lag linear baseline
3. gradient-boosted tree model if it materially improves performance
4. optional temporal neural model only if the evidence justifies the added complexity

Evaluation will include MAE, RMSE, sMAPE, peak-hour error, seasonal/hour-of-day slices, residual diagnostics, and rolling-origin validation.

## Documentation standard

GridPulse follows the portfolio-wide standard from day one:

**Markdown context → humanly commented code → output → Markdown interpretation → limitations / decision relevance.**

The first reviewer notebook lives at `notebooks/01_gridpulse_walkthrough.ipynb`. README visuals are generated by code and will be replaced with genuine EIA-result snapshots after the first authenticated live query is available.

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

### Use live EIA data — no manual download

1. Request an individual EIA API key.
2. Copy `.env.example` to `.env` and add the key, or configure `EIA_API_KEY` as a Streamlit secret.
3. Run the app:

```bash
streamlit run app.py
```

Choose the balancing-authority code and date window in the sidebar. GridPulse queries EIA API v2 directly, converts the JSON response to a pandas DataFrame in memory, enriches it with operational features, and caches the result for one hour. No CSV download is required for normal dashboard use.

If the key is missing or a live request fails, the application falls back to the clearly labeled synthetic development fixture.

### Optional reproducibility snapshot

A file snapshot is optional rather than part of the dashboard path. It is useful when a model experiment needs a frozen copy of the exact preliminary EIA observations used at that time:

```bash
python scripts/fetch_eia.py \
  --respondent PJM \
  --start 2025-01-01T00 \
  --end 2025-03-31T23 \
  --output data/processed/hourly_grid_snapshot.csv
```

The EIA client automatically paginates API v2 responses so longer analysis windows are not silently truncated at 5,000 rows.

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
│   ├── features.py
│   ├── stress.py
│   └── demo.py
├── scripts/
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
- Stress flags describe unusual combinations of observed signals and require interpretation.
- EIA-930 values are preliminary operating data and can contain missing/revised observations.
- Forecast comparisons must preserve time order; random train/test splits are not appropriate.
- More complex models are only retained when they improve out-of-time performance meaningfully.
