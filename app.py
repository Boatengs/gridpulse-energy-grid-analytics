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
from gridpulse.forecasting import (
    evaluate_reported_forecast,
    evaluate_seasonal_naive,
    peak_hour_metrics,
)
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
    "Downloaded EIA-930 data • demand • day-ahead forecast • ramping • "
    "generation mix • interchange • forecasting • operational stress screening"
)


def _configured_api_key() -> str | None:
    try:
        secret_key = st.secrets.get("EIA_API_KEY")
    except Exception:
        secret_key = None
    key = secret_key or os.getenv("EIA_API_KEY")
    return None if not key or key == "replace_me" else str(key)


@st.cache_data(show_spinner=False)
def load_processed_hourly(path: str) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    return frame.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_processed_fuel(path: str) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    return frame.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)


@st.cache_data(ttl=3600, show_spinner=False)
def load_live_grid_data(api_key: str, respondent: str, start: str, end: str) -> pd.DataFrame:
    raw = EIAClient(api_key=api_key).region_data(
        respondent=respondent, start=start, end=end
    )
    return add_stress_score(add_operational_features(raw)) if not raw.empty else raw


def prepare_demo() -> pd.DataFrame:
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
        "Recommended: freeze the downloaded EIA-930 files, prepare them once, "
        "and run every figure/model against the same snapshot."
    )

fuel_df: pd.DataFrame | None = None
demo_mode = False

if source_mode == "Downloaded EIA dataset":
    if PROCESSED_HOURLY.exists():
        df = load_processed_hourly(str(PROCESSED_HOURLY))
        if PROCESSED_FUEL.exists():
            fuel_df = load_processed_fuel(str(PROCESSED_FUEL))
        source_label = f"Frozen EIA-930 dataset · {PROCESSED_HOURLY}"
        st.success(f"Loaded {len(df):,} processed hourly rows.")
    else:
        df = prepare_demo()
        demo_mode = True
        source_label = "Synthetic fixture — downloaded EIA files not prepared yet"
        st.warning(
            "Processed EIA data are not present. The dashboard is showing the "
            "clearly labeled synthetic fixture until preparation is run."
        )
        st.code(
            "python scripts/prepare_downloaded_eia.py "
            "--balance-source data/raw/eia930 "
            "--respondent PJM"
        )
elif source_mode == "Live EIA API (optional)":
    with st.sidebar:
        respondent_query = st.text_input(
            "Balancing authority code", value=default_respondent
        ).strip().upper()
        selected_dates = st.date_input(
            "Analysis window",
            value=(default_start, default_end),
            max_value=date.today(),
        )
    start_date, end_date = (
        selected_dates
        if isinstance(selected_dates, tuple) and len(selected_dates) == 2
        else (selected_dates, selected_dates)
    )
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
            source_label = f"Live EIA-930 API · {respondent_query}"
        except Exception as exc:
            st.error(f"Live EIA request failed: {exc}")
            df = prepare_demo()
            demo_mode = True
            source_label = "Synthetic fallback after API failure"
    else:
        st.info("No EIA API key configured; showing the development fixture.")
        df = prepare_demo()
        demo_mode = True
        source_label = "Synthetic fixture — API key unavailable"
else:
    df = prepare_demo()
    demo_mode = True
    source_label = "Synthetic development fixture"

if "stress_score" not in df.columns:
    df = add_stress_score(add_operational_features(df))
df["period"] = pd.to_datetime(df["period"], utc=True)

respondents = sorted(df["respondent"].dropna().astype(str).unique())
selected = st.sidebar.selectbox("Balancing authority / region", respondents)
subset = df[df["respondent"].astype(str).eq(selected)].copy().sort_values("period")

if fuel_df is not None:
    fuel_subset = fuel_df[fuel_df["respondent"].astype(str).eq(selected)].copy()
else:
    fuel_subset = None

qa = hourly_qa_summary(subset)
with st.sidebar.expander("Data QA", expanded=not demo_mode):
    st.write(f"Rows: **{qa.get('rows', 0):,}**")
    st.write(f"Missing UTC slots: **{qa.get('missing_hour_slots', 0):,}**")
    st.write(f"Duplicate hours: **{qa.get('duplicate_hours', 0):,}**")
    st.write(f"Missing demand: **{qa.get('missing_demand', 0):,}**")
    st.write(f"Missing forecast: **{qa.get('missing_forecast', 0):,}**")
    st.write(f"Missing interchange: **{qa.get('missing_interchange', 0):,}**")
    if "demand_imputed" in qa:
        st.write(f"Imputed demand hours: **{qa.get('demand_imputed', 0):,}**")

max_hours = max(1, len(subset))
default_hours = min(24 * 30, max_hours)
min_hours = min(24, max_hours)
window = (
    st.sidebar.slider(
        "Hours to display",
        min_hours,
        max_hours,
        default_hours,
        step=min(24, max_hours - min_hours),
    )
    if max_hours > min_hours
    else max_hours
)
view = subset.tail(window).copy()

forecast_mae = view["abs_forecast_error_mw"].mean()
peak = view["demand_mw"].max()
max_ramp = view["demand_ramp_pct"].abs().max()
max_stress = view["stress_score"].max()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Peak demand", f"{peak:,.0f} MW")
c2.metric("Forecast MAE", f"{forecast_mae:,.0f} MW" if pd.notna(forecast_mae) else "N/A")
c3.metric("Max hourly ramp", f"{max_ramp:.1f}%" if pd.notna(max_ramp) else "N/A")
c4.metric("Max stress signal", f"{max_stress:.0f}/100" if pd.notna(max_stress) else "N/A")

st.subheader("Demand vs day-ahead forecast")
fig = go.Figure()
fig.add_trace(go.Scatter(x=view["period"], y=view["demand_mw"], name="Actual demand", mode="lines"))
fig.add_trace(go.Scatter(x=view["period"], y=view["forecast_mw"], name="Day-ahead forecast", mode="lines"))
fig.update_layout(height=420, yaxis_title="MW", xaxis_title=None, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)
st.markdown(
    "**What this shows:** high demand and forecast misses are separate operating "
    "questions; the overlay makes it possible to see when they occur together."
)

left, right = st.columns(2)
with left:
    st.subheader("Forecast-error distribution")
    err_fig = px.histogram(
        view,
        x="forecast_error_mw",
        nbins=35,
        labels={"forecast_error_mw": "Actual − forecast (MW)"},
    )
    err_fig.add_vline(x=0, line_dash="dash")
    st.plotly_chart(err_fig, use_container_width=True)
    st.markdown(
        "**What this shows:** positive errors are under-forecasts; negative errors "
        "are over-forecasts. Missing EIA forecast rows remain missing."
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
        "**What this shows:** ramps isolate how quickly demand changes, not simply "
        "how high demand is. Extreme ramps should be checked against the QA evidence."
    )

st.subheader("Demand heatmap")
heat = (
    view.assign(date=view["period"].dt.date, hour=view["period"].dt.hour)
    .pivot_table(index="date", columns="hour", values="demand_mw", aggfunc="mean")
)
heat_fig = px.imshow(
    heat,
    aspect="auto",
    labels={"x": "Hour UTC", "y": "Date", "color": "Demand (MW)"},
)
st.plotly_chart(heat_fig, use_container_width=True)
st.markdown(
    "**What this shows:** recurring intraday load shapes and unusual days are easier "
    "to inspect than in a raw hourly table."
)

st.subheader("Operational stress signal")
stress_fig = px.area(
    view,
    x="period",
    y="stress_score",
    labels={"stress_score": "Stress screening score"},
    range_y=[0, 100],
)
stress_fig.add_hline(y=65, line_dash="dash", annotation_text="High-screening threshold")
st.plotly_chart(stress_fig, use_container_width=True)
st.markdown(
    "**What this shows:** a transparent screening signal combining demand level, "
    "forecast error, ramping, and interchange dependence. Missing components are "
    "reweighted rather than treated as zero. This is not an EIA/NERC reliability "
    "rating and does not predict blackouts."
)

left, right = st.columns(2)
with left:
    st.subheader("Net generation and interchange")
    long = view.melt(
        id_vars="period",
        value_vars=["net_generation_mw", "total_interchange_mw"],
        var_name="series",
        value_name="mw",
    )
    gen_fig = px.line(long, x="period", y="mw", color="series", labels={"mw": "MW"})
    st.plotly_chart(gen_fig, use_container_width=True)
    st.markdown(
        "**What this shows:** generation and interchange provide supply context around "
        "high-demand and high-stress hours."
    )
with right:
    st.subheader("Highest-stress hours")
    cols = [
        c for c in [
            "period", "demand_mw", "abs_forecast_error_mw", "demand_ramp_pct",
            "total_interchange_mw", "stress_score", "stress_band",
            "stress_components_available", "balance_residual_mw"
        ] if c in view
    ]
    events = view.nlargest(min(10, len(view)), "stress_score")[cols]
    st.dataframe(events, use_container_width=True, hide_index=True)
    st.markdown(
        "**What this shows:** the event table turns the composite score back into "
        "inspectable operating evidence instead of asking reviewers to trust one number."
    )

if fuel_subset is not None and not fuel_subset.empty:
    st.subheader("Generation mix")
    fuel_view = fuel_subset[
        fuel_subset["period"].between(view["period"].min(), view["period"].max())
    ].copy()
    preferred = [
        "nuclear", "natural_gas", "coal", "wind", "solar", "hydro_pumped",
        "petroleum", "other_fuel"
    ]
    fuel_view = fuel_view[fuel_view["fuel_type"].isin(preferred)]
    fuel_fig = px.area(
        fuel_view,
        x="period",
        y="generation_mw",
        color="fuel_type",
        labels={"generation_mw": "Generation (MW)", "fuel_type": "Fuel"},
    )
    st.plotly_chart(fuel_fig, use_container_width=True)
    st.markdown(
        "**What this shows:** the supply mix around demand peaks and forecast misses. "
        "GridPulse reconciles EIA's mid-2024 fuel-schema change before plotting."
    )

    renewable = (
        fuel_subset[fuel_subset["fuel_type"].isin(["wind", "solar", "hydro_pumped"])]
        .groupby("period", as_index=False)["generation_mw"].sum()
        .rename(columns={"generation_mw": "renewable_mw"})
    )
    total = (
        fuel_subset.groupby("period", as_index=False)["generation_mw"].sum()
        .rename(columns={"generation_mw": "reported_fuel_generation_mw"})
    )
    share = renewable.merge(total, on="period", how="inner")
    share["renewable_share_pct"] = (
        share["renewable_mw"].clip(lower=0)
        / share["reported_fuel_generation_mw"].replace(0, np.nan)
        * 100
    )
    share = share[share["period"].between(view["period"].min(), view["period"].max())]
    st.subheader("Renewable generation share")
    share_fig = px.line(
        share,
        x="period",
        y="renewable_share_pct",
        labels={"renewable_share_pct": "Reported renewable share (%)"},
    )
    st.plotly_chart(share_fig, use_container_width=True)
    st.markdown(
        "**What this shows:** a descriptive share of reported wind, solar, and "
        "hydro/pumped-storage generation. It is portfolio context, not a reliability score."
    )

if not demo_mode and len(subset) >= 24 * 21:
    years = sorted(subset["period"].dt.year.unique())
    test_start = pd.Timestamp(f"{years[-1]}-01-01", tz="UTC") if len(years) > 1 else subset["period"].quantile(0.8)
    naive_holdout, naive_metrics = evaluate_seasonal_naive(subset, test_start)
    eia_holdout, eia_metrics = evaluate_reported_forecast(subset, test_start)
    naive_peak = peak_hour_metrics(naive_holdout)
    eia_peak = peak_hour_metrics(
        eia_holdout.assign(reported_forecast_pred_mw=eia_holdout["forecast_mw"]),
        predicted_column="reported_forecast_pred_mw",
    )

    st.subheader("Out-of-time forecasting benchmark")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("EIA day-ahead MAE", f"{eia_metrics['mae']:,.0f} MW")
    m2.metric("Weekly-naive MAE", f"{naive_metrics['mae']:,.0f} MW")
    m3.metric("EIA peak-hour MAE", f"{eia_peak['mae']:,.0f} MW")
    m4.metric("Naive peak-hour MAE", f"{naive_peak['mae']:,.0f} MW")
    compare = pd.DataFrame(
        {
            "model": ["EIA day-ahead", "Same hour last week"],
            "MAE": [eia_metrics["mae"], naive_metrics["mae"]],
            "RMSE": [eia_metrics["rmse"], naive_metrics["rmse"]],
            "sMAPE": [eia_metrics["smape"], naive_metrics["smape"]],
        }
    )
    st.dataframe(compare, use_container_width=True, hide_index=True)
    st.markdown(
        f"**What this shows:** both forecasts are evaluated only from **{pd.Timestamp(test_start).date()}** "
        "forward. The weekly-naive model is a deliberately simple benchmark; any future "
        "machine-learning model must beat it out of time, especially on peak-demand hours."
    )

st.caption(
    f"Data source mode: {source_label}. EIA-930 operating values are shown in MW. "
    "Downloaded raw files remain outside Git; processed data are reproducible from the source snapshot."
)
