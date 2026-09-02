# Data handling

GridPulse is **API-first**. The Streamlit dashboard queries EIA API v2 directly and does not require a manually downloaded dataset.

- `data/raw/` — reserved for approved external snapshots if a future audit requires them.
- `data/processed/` — reserved for optional reproducibility/model snapshots, not the normal dashboard path.

The production dashboard converts EIA JSON responses directly to pandas DataFrames in memory and uses Streamlit caching to reduce repeated API calls. Large, sensitive, or credential-bearing files should never be committed.
