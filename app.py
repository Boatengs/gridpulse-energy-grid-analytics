from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from gridpulse.demo import make_demo_data
from gridpulse.eia import EIAClient
from gridpulse.features import add_operational_features
from gridpulse.forecasting import evaluate_seasonal_naive, peak_hour_metrics
from gridpulse.io import hourly_qa_summary
from gridpulse.stress import add_stress_score

st.set_page_config(page_title="GridPulse", page_icon="⚡", layout="wide")
load_dotenv()

PROCESSED_HOURLY = Path(
    os.getenv("GRIDPULSE_HOURLY_PATH", "data/processed/gridpulse_hourly.parquet")
)
PROCESSED_FUEL = Path(
    os.getenv("GRIDPULSE_FUEL_PATH", "data/processed/gridpulse_fuel_mix.parquet")
)

st.title("GridPulse — Energy Demand & Grid Stress Analytics")
st.caption(
    "Downloaded EIA-930 data • demand • forecast error • ramping • generation mix • "
    "interchange • forecasting • operational stress screening"
)


def _configured_api_key() -> str | None:
    """Keep API access available as an optional route, never as a requirement."""
    try:
        secret_key = st.secrets.get("EIA_API_KEY")
    except Exception:
        secret_key = None
    env_key = os.getenv("EIA_API_KEY")
    key = secret_key or env_key
    if not key or key == "replace_me":
        return None
    return str(key)


@st.cache_data(show_spinner=False)
def load_processed_hourly(path: str) -> pd.DataFrame:
    """Load the frozen analytical table built from downloaded EIA CSV exports."""
    frame = pd.read_parquet(path)
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    return frame.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_processed_fuel(path: str) -> pd.DataFrame:
    """Load generation-by-fuel data when the companion export has been prepared."""
    frame = pd.read_parquet(path)
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    return frame.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_live_grid_data(
    api_key: str,
    respondent: str,
    start: str,
    end: str,
) -> pd.DataFrame:
    """Optional API path retained for experimentation and recent-data checks."""
    raw = EIAClient(api_key=api_key).region_data(
        respondent=respondent,
        start=start,
        end=end,
    )
    if raw.empty:
        return raw
    return add_stress_score(add_operational_features(raw))


def _prepare_demo() -> pd.DataFrame:
    return add_stress_score(add_operational_features(make_demo_data()))


api_key = _configured_api_key()
default_respondent = os.getenv("GRIDPULSE_RESPONDENT", "PJM")
default_end = date.today() - timedelta(days=1)
default_start = default_end - timedelta(days=13)

with st.sidebar:
    st.header("Data source")
    source_mode = st.selectbox(
        "Run GridPulse with",
        [
            "Downloaded EIA dataset",
            "Live EIA API (optional)",
            "Synthetic development fixture",
        ],
        index=0,
    )
    st.caption(
        "Recommended production path: download EIA exports once, normalize them to "
        "Parquet, and run every dashboard/model experiment against the same frozen data."
    )

fuel_df: pd.DataFrame | None = None
demo_mode = False

if source_mode == "Downloaded EIA dataset":
    if PROCESSED_HOURLY.exists():
        df = load_processed_hourly(str(PROCESSED_HOURLY))
        if PROCESSED_FUEL.exists():
            fuel_df = load_processed_fuel(str(PROCESSED_FUEL))
        source_label = f"Frozen downloaded EIA-930 dataset · {PROCESSED_HOURLY}"
        st.success(f"Loaded {len(df):,} processed hourly rows from the local EIA dataset.")
    else:
        df = _prepare_demo()
        demo_mode = True
        source_label = "Synthetic development fixture — downloaded EIA data not prepared yet"
        st.warning(
            "The processed EIA dataset is not present yet. GridPulse is showing the "
            "synthetic development fixture until the downloaded files are prepared."
        )
        st.code(
            "python scripts/prepare_downloaded_eia.py "
            "--region-source data/raw/eia930/region "
            "--fuel-source data/raw/eia930/fuel"
        )
elif source_mode == "Live EIA API (optional)":
    with st.sidebar:
        respondent_query = st.text_input(
            "Balancing authority code",
            value=default_respondent,
        ).strip().upper()
        selected_dates = st.date_input(
            "Analysis window",
            value=(default_start, default_end),
            max_value=date.today(),
        )
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        start_date, end_date = selected_dates
    else:
        start_date = end_date = selected_dates
    if api_key and respondent_query:
        try:
            with st.spinner("Querying EIA-930 directly…"):
                df = load_live_grid_data(
                    api_key,
                    respondent_query,
                    f"{start_date.isoformat()}T00",
                    f"{end_date.isoformat()}T23",
                )
            if df.empty:
                raise ValueError("EIA returned no rows for the selected window.")
            source_label = (
                f"Live EIA-930 API · {respondent_query} · "
                f"{start_date} to {end_date}"
            )
            st.success(f"Loaded {len(df):,} hourly rows from the optional API route.")
        except Exception as exc:
            df = _prepare_demo()
            demo_mode = True
            source_label = "Synthetic fallback after live API failure"
            st.error(f"Live EIA request failed: {exc}")
    else:
        df = _prepare_demo()
        demo_mode = True
        source_label = "Synthetic fallback — EIA API key is not configured"
        st.info("No API key is configured. The downloaded-data route does not require one.")
else:
    df = _prepare_demo()
    demo_mode = True
    source_label = "Synthetic development fixture"

if "stress_score" not in df.columns:
    df = add_stress_score(add_operational_features(df))
df["period"] = pd.to_datetime(df["period"], utc=True, errors="coerce")
df = df.dropna(subset=["period"]).copy()

if demo_mode:
    st.warning(
        "Demo mode: these values are synthetic and only exercise the analytical "
        "pipeline. They are not EIA findings."
    )

respondents = sorted(df["respondent"].dropna().astype(str).unique())
selected = st.sidebar.selectbox(
    "Balancing authority / region",
    respondents,
    index=respondents.index(default_respondent)
    if default_respondent in respondents
    else 0,
)
subset = df[df["respondent"].astype(str) == selected].copy()
if fuel_df is not None:
    fuel_subset = fuel_df[fuel_df["respondent"].astype(str) == selected].copy()
else:
    fuel_subset = None

max_hours = max(1, len(subset))
default_hours = min(24 * 30, max_hours)
min_hours = min(24, max_hours)
if max_hours > min_hours:
    window = st.sidebar.slider(
        "Hours to display",
        min_hours,
        max_hours,
        default_hours,
        step=min(24, max_hours - min_hours),
    )
else:
    window = max_hours
view = subset.tail(window).copy()

qa = hourly_qa_summary(subset)
with st.sidebar.expander("Data QA"):
    st.write(f"Rows: **{qa['rows']:,}**")
    st.write(f"Missing hourly slots: **{qa['missing_hour_slots']:,}**")
    st.write(f"Duplicate respondent-hours: **{qa['duplicate_hours']:,}**")
    st.write(f"Missing demand values: **{qa['missing_demand']:,}**")
    st.write(f"Non-positive demand values: **{qa['nonpositive_demand']:,}**")

forecast_mae = view.get(
    "abs_forecast_error_mwh",
    pd.Series(dtype=float),
).mean()
peak = view["demand_mwh"].max()
max_ramp = view.get(
    "demand_ramp_pct",
    pd.Series(dtype=float),
).abs().max()
max_stress = view["stress_score"].max()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Peak demand", f"{peak:,.0f} MWh")
c2.metric(
    "Forecast MAE",
    f"{forecast_mae:,.0f} MWh" if pd.notna(forecast_mae) else "N/A",
)
c3.metric(
    "Max hourly ramp",
    f"{max_ramp:.1f}%" if pd.notna(max_ramp) else "N/A",
)
c4.metric("Max stress signal", f"{max_stress:.0f}/100")

st.subheader("Demand vs day-ahead forecast")
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=view["period"],
        y=view["demand_mwh"],
        name="Actual demand",
        mode="lines",
    )
)
if "forecast_mwh" in view:
    fig.add_trace(
        go.Scatter(
            x=view["period"],
            y=view["forecast_mwh"],
            name="Day-ahead forecast",
            mode="lines",
        )
    )
fig.update_layout(
    height=430,
    yaxis_title="MWh",
    xaxis_title=None,
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)
st.markdown(
    "**What this shows:** the operational question is not only whether demand is high, "
    "but whether demand is diverging from the day-ahead expectation at the same time."
)

left, right = st.columns(2)
with left:
    st.subheader("Forecast-error distribution")
    if "forecast_error_mwh" in view:
        err_fig = px.histogram(
            view,
            x="forecast_error_mwh",
            nbins=40,
            labels={"forecast_error_mwh": "Actual − forecast (MWh)"},
        )
        err_fig.add_vline(x=0, line_dash="dash")
        st.plotly_chart(err_fig, use_container_width=True)
        st.markdown(
            "**What this shows:** positive errors are hours when demand exceeded the "
            "day-ahead forecast; negative errors are over-forecasting."
        )

with right:
    st.subheader("Demand ramping")
    ramp_fig = px.line(
        view,
        x="period",
        y="demand_ramp_pct",
        labels={"demand_ramp_pct": "Hour-over-hour demand change (%)"},
    )
    st.plotly_chart(ramp_fig, use_container_width=True)
    st.markdown(
        "**What this shows:** rapid ramps can create a different operating challenge "
        "than a gradually rising peak, even at the same final demand level."
    )

st.subheader("Demand heatmap")
heat = (
    view.assign(date=view["period"].dt.date, hour=view["period"].dt.hour)
    .pivot_table(
        index="date",
        columns="hour",
        values="demand_mwh",
        aggfunc="mean",
    )
)
heat_fig = px.imshow(
    heat,
    aspect="auto",
    labels={"x": "Hour UTC", "y": "Date", "color": "Demand (MWh)"},
)
st.plotly_chart(heat_fig, use_container_width=True)
st.markdown(
    "**What this shows:** recurring intraday load shape, unusual peak windows, and "
    "days that depart from the typical pattern become much easier to spot."
)

st.subheader("Operational stress signal")
stress_fig = px.area(
    view,
    x="period",
    y="stress_score",
    labels={"stress_score": "Stress screening score"},
    range_y=[0, 100],
)
stress_fig.add_hline(
    y=65,
    line_dash="dash",
    annotation_text="High-screening threshold",
)
st.plotly_chart(stress_fig, use_container_width=True)
st.markdown(
    "**What this shows:** this transparent signal combines demand level, forecast "
    "error, ramping, and interchange dependence. It is not an EIA/NERC reliability "
    "rating and does not predict blackouts."
)

left, right = st.columns(2)
with left:
    st.subheader("Net generation and interchange")
    gen_cols = [
        c
        for c in ["net_generation_mwh", "total_interchange_mwh"]
        if c in view
    ]
    if gen_cols:
        long = view.melt(
            id_vars="period",
            value_vars=gen_cols,
            var_name="series",
            value_name="mwh",
        )
        gen_fig = px.line(
            long,
            x="period",
            y="mwh",
            color="series",
            labels={"mwh": "MWh", "series": "Series"},
        )
        st.plotly_chart(gen_fig, use_container_width=True)
    st.markdown(
        "**What this shows:** local generation and interchange stay visible so "
        "high-demand periods can be interpreted in supply context."
    )

with right:
    st.subheader("Highest-stress hours")
    cols = [
        c
        for c in [
            "period",
            "demand_mwh",
            "abs_forecast_error_mwh",
            "demand_ramp_pct",
            "total_interchange_mwh",
            "stress_score",
            "stress_band",
        ]
        if c in view
    ]
    events = view.nlargest(min(10, len(view)), "stress_score")[cols]
    st.dataframe(events, use_container_width=True, hide_index=True)
    st.markdown(
        "**What this shows:** the composite signal is returned to its underlying "
        "evidence so a reviewer can inspect why an hour was flagged."
    )

if fuel_subset is not None and not fuel_subset.empty:
    st.divider()
    st.subheader("Generation mix by energy source")
    fuel_view = fuel_subset[
        fuel_subset["period"].between(view["period"].min(), view["period"].max())
    ].copy()
    if not fuel_view.empty:
        top_fuels = (
            fuel_view.groupby("fuel_type")["generation_mwh"]
            .sum()
            .abs()
            .nlargest(8)
            .index
        )
        fuel_view = fuel_view[fuel_view["fuel_type"].isin(top_fuels)]
        fuel_fig = px.area(
            fuel_view,
            x="period",
            y="generation_mwh",
            color="fuel_type",
            labels={
                "generation_mwh": "Net generation (MWh)",
                "fuel_type": "Energy source",
            },
        )
        fuel_fig.update_layout(height=500, hovermode="x unified")
        st.plotly_chart(fuel_fig, use_container_width=True)
        st.markdown(
            "**What this shows:** the generation mix reveals which energy sources "
            "expand or contract around demand peaks, ramps, and high-stress screening hours."
        )

    renewable_tokens = (
        "wind",
        "solar",
        "hydro",
        "geothermal",
        "biomass",
    )
    renewable_mask = fuel_subset["fuel_type"].str.lower().apply(
        lambda value: any(token in value for token in renewable_tokens)
    )
    renewable_hourly = (
        fuel_subset.assign(
            renewable=np.where(
                renewable_mask,
                fuel_subset["generation_mwh"],
                0.0,
            )
        )
        .groupby("period", as_index=False)
        .agg(
            renewable_mwh=("renewable", "sum"),
            total_generation_mwh=("generation_mwh", "sum"),
        )
    )
    renewable_hourly["renewable_share_pct"] = (
        renewable_hourly["renewable_mwh"]
        / renewable_hourly["total_generation_mwh"].replace(0, np.nan)
        * 100
    )
    renewable_view = renewable_hourly[
        renewable_hourly["period"].between(view["period"].min(), view["period"].max())
    ]
    if not renewable_view.empty:
        renewable_fig = px.line(
            renewable_view,
            x="period",
            y="renewable_share_pct",
            labels={"renewable_share_pct": "Renewable share of generation (%)"},
        )
        renewable_fig.update_layout(height=360)
        st.plotly_chart(renewable_fig, use_container_width=True)
        st.markdown(
            "**What this shows:** this descriptive share helps connect the operating "
            "story to changes in the generation portfolio. It is not a measure of "
            "reliability by itself."
        )

st.divider()
st.subheader("Forecasting baseline — same hour last week")
if len(subset) >= 24 * 21:
    candidate_cutoff = subset["period"].max() - pd.Timedelta(days=30)
    holdout, baseline_metrics = evaluate_seasonal_naive(
        subset,
        test_start=candidate_cutoff,
    )
    peak_metrics = peak_hour_metrics(holdout)

    b1, b2, b3, b4 = st.columns(4)
    b1.metric("Baseline MAE", f"{baseline_metrics['mae']:,.0f} MWh")
    b2.metric("Baseline RMSE", f"{baseline_metrics['rmse']:,.0f} MWh")
    b3.metric("Baseline sMAPE", f"{baseline_metrics['smape']:.2f}%")
    b4.metric("Peak-hour MAE", f"{peak_metrics['mae']:,.0f} MWh")

    baseline_plot = holdout.tail(min(len(holdout), 24 * 14))
    baseline_fig = go.Figure()
    baseline_fig.add_trace(
        go.Scatter(
            x=baseline_plot["period"],
            y=baseline_plot["demand_mwh"],
            name="Actual",
            mode="lines",
        )
    )
    baseline_fig.add_trace(
        go.Scatter(
            x=baseline_plot["period"],
            y=baseline_plot["seasonal_naive_pred_mwh"],
            name="Same hour last week",
            mode="lines",
        )
    )
    baseline_fig.update_layout(
        height=430,
        hovermode="x unified",
        yaxis_title="MWh",
    )
    st.plotly_chart(baseline_fig, use_container_width=True)
    st.markdown(
        "**What this tells us:** this is the minimum forecasting bar. More complex "
        "models only earn a place in GridPulse if they beat this out-of-time baseline, "
        "including during high-demand hours."
    )
else:
    st.info(
        "At least three weeks of hourly data are needed before the same-hour-last-week "
        "baseline is meaningful."
    )

st.caption(
    f"Data source mode: {source_label}. Downloaded EIA data is the recommended "
    "production path; live API access remains optional."
)
