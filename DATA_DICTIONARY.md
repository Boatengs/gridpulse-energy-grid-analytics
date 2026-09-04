# Data Dictionary

GridPulse's primary downloaded EIA-930 BALANCE workflow uses **MW** for hourly operating power values.

| Field | Meaning |
|---|---|
| `period` | End-of-hour timestamp normalized to UTC |
| `local_time` | EIA local time at end of hour |
| `hour_number` | EIA source hour number |
| `respondent` | Balancing-authority code, currently PJM |
| `region` | EIA source region label |
| `forecast_mw` | Reported day-ahead demand forecast (MW) |
| `demand_mw` | Adjusted demand when available, otherwise reported demand (MW) |
| `net_generation_mw` | Adjusted net generation when available (MW) |
| `total_interchange_mw` | Adjusted total interchange when available (MW) |
| `demand_imputed` | Whether the EIA imputed demand field supplied the adjusted record |
| `generation_imputed` | Whether the EIA imputed generation field supplied the adjusted record |
| `interchange_imputed` | Whether the EIA imputed interchange field supplied the adjusted record |
| `source_file` | Original six-month BALANCE filename |
| `demand_change_mw` | Hour-over-hour demand change (MW) |
| `demand_ramp_pct` | Hour-over-hour percentage demand change |
| `demand_percentile` | Demand percentile within the current analytical table |
| `forecast_error_mw` | Actual demand minus day-ahead forecast (MW) |
| `abs_forecast_error_mw` | Absolute forecast error (MW) |
| `abs_forecast_error_pct` | Absolute forecast error divided by actual demand |
| `interchange_share` | Absolute interchange divided by absolute demand |
| `balance_residual_mw` | Net generation − demand − total interchange; used as a QA diagnostic |
| `qa_demand_step_pct` | Exact-hour demand change used by the source-data QA rules |
| `qa_large_demand_step` | Whether the exact-hour demand step exceeds the current QA threshold |
| `qa_isolated_demand_discontinuity` | Whether a large demand step is immediately reversed in the following hour |
| `qa_large_balance_residual` | Whether the absolute balance residual exceeds the current QA threshold |
| `qa_anomaly` | Combined non-mutating QA flag for suspicious source-data events |
| `qa_anomaly_reason` | Plain-language reason attached to a flagged QA hour |
| `stress_score` | 0–100 transparent operational screening score |
| `stress_band` | Normal/elevated/high/very-high screening band |
| `stress_components_available` | Number of non-missing score components available for that hour |
| `stress_component_weight` | Total component weight represented in that hour's score |

QA fields are diagnostic. They do not replace, smooth, clip, interpolate, or delete the reported EIA operating values.

## Fuel table

| Field | Meaning |
|---|---|
| `period` | UTC end-of-hour timestamp |
| `respondent` | Balancing-authority code |
| `fuel_type` | Normalized fuel category |
| `generation_mw` | Reported/adjusted generation for that category (MW) |

Normalized fuel categories include `natural_gas`, `nuclear`, `coal`, `wind`, `solar`, `hydro_pumped`, `petroleum`, `other_fuel`, and storage/geothermal categories when reported.
