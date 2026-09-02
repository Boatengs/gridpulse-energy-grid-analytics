# Data Dictionary

| Field | Meaning |
|---|---|
| `period` | Hourly timestamp normalized to UTC |
| `respondent` | EIA balancing authority or region code |
| `respondent-name` | EIA respondent display name |
| `demand_mwh` | Reported hourly electricity demand |
| `forecast_mwh` | Day-ahead demand forecast |
| `net_generation_mwh` | Net generation reported for the respondent |
| `total_interchange_mwh` | Net interchange reported by the respondent |
| `demand_change_mwh` | Hour-over-hour demand change |
| `demand_ramp_pct` | Hour-over-hour percentage demand change |
| `demand_percentile` | Demand rank percentile within the analysis table |
| `forecast_error_mwh` | Actual demand minus forecast demand |
| `abs_forecast_error_mwh` | Absolute day-ahead forecast miss |
| `abs_forecast_error_pct` | Absolute forecast miss divided by actual demand |
| `interchange_share` | Absolute interchange divided by absolute demand |
| `stress_score` | 0–100 transparent screening score |
| `stress_band` | Normal/elevated/high/very-high screening band |
