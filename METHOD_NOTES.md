# Method Notes

## Source
Primary source: U.S. Energy Information Administration Form EIA-930, accessed through API v2 `electricity/rto` routes.

## Phase 1 metric codes
- `D` — demand
- `DF` — day-ahead demand forecast
- `NG` — net generation
- `TI` — total interchange

## Forecast-error definition
`forecast_error_mwh = actual demand - day-ahead forecast`

Positive values mean actual demand was higher than forecast. Absolute error is used for accuracy summaries; signed error is retained for bias diagnostics.

## Demand ramp
Hour-over-hour percent change in demand. Ramps are inspected separately from demand level because a rapid change can be operationally relevant even when demand is below the historical maximum.

## Operational-stress screening
The Phase 1 score is deliberately transparent:

- 40% demand percentile
- 25% absolute forecast-error percentile
- 20% normalized absolute hourly demand ramp
- 15% interchange-dependence percentile

The thresholds and weights are provisional screening assumptions. They are not reliability standards and must be sensitivity-tested before any stronger interpretation.

## Forecasting roadmap
1. seasonal naive baseline
2. linear/calendar baseline
3. tree model with lag/calendar/weather features if justified
4. rolling-origin validation
5. peak-hour and seasonal error slices
6. SHAP only if the tree model earns its complexity
