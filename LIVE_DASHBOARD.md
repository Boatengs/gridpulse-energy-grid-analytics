# GridPulse Live Animated Dashboard

GridPulse now includes a multipage Streamlit control room at:

```text
pages/1_Live_Control_Room.py
```

Start the project normally:

```bash
streamlit run app.py
```

Then select **Live Control Room** from Streamlit's page navigation.

## What is live vs animated

The control room deliberately separates two ideas:

- **Live EIA API mode** re-queries EIA-930 on a short cadence (about every five minutes when auto-refresh is enabled).
- **Animated replay** runs locally in the browser and replays the selected hourly operating window with Play/Pause controls.

EIA-930 is an hourly operational data source, not sub-second SCADA telemetry. The page therefore displays the timestamp and age of the latest observation and labels the feed as Fresh, Delayed, or Stale rather than pretending every observation is instantaneous.

## Modes

### Frozen PJM replay

Uses the prepared local file:

```text
data/processed/gridpulse_hourly.parquet
```

This is the reproducible portfolio mode. It supports animated historical playback with no API key.

If the prepared Parquet file is unavailable, the page clearly falls back to the synthetic development fixture rather than presenting synthetic values as PJM observations.

### Live EIA API

Set an EIA API key in either the environment:

```bash
export EIA_API_KEY="your_key"
```

or Streamlit secrets:

```toml
# .streamlit/secrets.toml — do not commit this file
EIA_API_KEY = "your_key"
```

The page then queries EIA API v2 `electricity/rto/region-data` for demand, day-ahead forecast, net generation, and total interchange.

When **Auto-refresh live feed** is enabled, the live panel reruns approximately every five minutes. API responses are cached for four minutes to avoid unnecessary repeated calls.

### Synthetic demo

A clearly labeled development fixture used only when real source data are intentionally unavailable.

## Control-room surfaces

The page includes:

- feed freshness badge with latest UTC timestamp and observation age,
- current demand,
- current EIA forecast,
- current forecast error,
- hourly demand ramp,
- current GridPulse stress-screen value,
- animated demand-versus-EIA replay with browser-side Play/Pause,
- playback-speed control,
- operational stress gauge,
- net generation and interchange readouts,
- recent pulse timeline,
- highest-stress recent events,
- source-data QA watch,
- the verified 2025 GridPulse-vs-EIA model result as historical context.

The live page does **not** claim that the historical ML improvement automatically applies to each incoming live hour.

## Public deployment

A simple deployment target is Streamlit Community Cloud or another Python host capable of running Streamlit.

For a public live deployment:

1. deploy this GitHub repository with `app.py` as the Streamlit entry point,
2. add `EIA_API_KEY` as a deployment secret,
3. do not commit `.streamlit/secrets.toml`,
4. use the **Live EIA API** page mode for current observations,
5. keep the frozen raw and processed EIA datasets outside Git unless the project's data-publication policy changes.

A hosting service must be configured outside the repository; GitHub Actions in this project currently validates code but does not publish a persistent Streamlit server.

## Interpretation boundary

The operational stress score is a transparent analytical screen combining demand, forecast error, ramping, and interchange dependence. It is not an official EIA/NERC reliability rating and GridPulse does not predict blackouts.
