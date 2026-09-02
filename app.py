from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from gridpulse.demo import make_demo_data
from gridpulse.features import add_operational_features
from gridpulse.stress import add_stress_score

st.set_page_config(page_title="GridPulse", page_icon="⚡", layout="wide")
load_dotenv()

st.title("GridPulse — Energy Demand & Grid Stress Analytics")
st.caption("Demand • forecast error • ramping • generation • interchange • transparent operational-stress screening")

DATA_PATH = Path("data/processed/hourly_grid.csv")
if DATA_PATH.exists():
    df = pd.read_csv(DATA_PATH, parse_dates=["period"])
    source_label = "EIA-930 processed data"
    demo_mode = False
else:
    df = make_demo_data()
    source_label = "Synthetic development fixture — replace with an authenticated EIA pull"
    demo_mode = True

if "stress_score" not in df.columns:
    df = add_stress_score(add_operational_features(df))

df["period"] = pd.to_datetime(df["period"], utc=True)

if demo_mode:
    st.warning("Demo mode: these values are synthetic and exist only to exercise the analytical and dashboard pipeline. They are not EIA findings.")
else:
    st.success(f"Loaded {len(df):,} hourly rows from {source_label}.")

respondents = sorted(df.get("respondent", pd.Series(["ALL"])).dropna().astype(str).unique())
selected = st.sidebar.selectbox("Balancing authority / region", respondents)
window = st.sidebar.slider("Hours to display", 48, min(24 * 30, len(df)), min(24 * 14, len(df)), step=24)
view = df[df.get("respondent", selected).astype(str) == selected].tail(window).copy()

latest = view.iloc[-1]
forecast_mae = view.get("abs_forecast_error_mwh", pd.Series(dtype=float)).mean()
peak = view["demand_mwh"].max()
max_ramp = view.get("demand_ramp_pct", pd.Series(dtype=float)).abs().max()
max_stress = view["stress_score"].max()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Peak demand", f"{peak:,.0f} MWh")
c2.metric("Forecast MAE", f"{forecast_mae:,.0f} MWh" if pd.notna(forecast_mae) else "N/A")
c3.metric("Max hourly ramp", f"{max_ramp:.1f}%" if pd.notna(max_ramp) else "N/A")
c4.metric("Max stress signal", f"{max_stress:.0f}/100")

st.subheader("Demand vs day-ahead forecast")
fig = go.Figure()
fig.add_trace(go.Scatter(x=view["period"], y=view["demand_mwh"], name="Actual demand", mode="lines"))
if "forecast_mwh" in view:
    fig.add_trace(go.Scatter(x=view["period"], y=view["forecast_mwh"], name="Day-ahead forecast", mode="lines"))
fig.update_layout(height=420, yaxis_title="MWh", xaxis_title=None, hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)
st.markdown("**What this shows:** the operational question is not only whether demand is high, but whether demand is diverging from the day-ahead expectation at the same time.")

left, right = st.columns(2)
with left:
    st.subheader("Forecast-error distribution")
    if "forecast_error_mwh" in view:
        err_fig = px.histogram(view, x="forecast_error_mwh", nbins=35, labels={"forecast_error_mwh": "Actual − forecast (MWh)"})
        err_fig.add_vline(x=0, line_dash="dash")
        st.plotly_chart(err_fig, use_container_width=True)
        st.markdown("**What this shows:** large positive errors represent hours when actual demand exceeded the day-ahead forecast; large negative errors represent over-forecasting.")

with right:
    st.subheader("Demand ramping")
    ramp_fig = px.line(view, x="period", y="demand_ramp_pct", labels={"demand_ramp_pct": "Hour-over-hour demand change (%)"})
    st.plotly_chart(ramp_fig, use_container_width=True)
    st.markdown("**What this shows:** rapid ramps can create a different operating challenge than a gradually rising peak, even when the final demand level is similar.")

st.subheader("Demand heatmap")
heat = view.assign(date=view["period"].dt.date, hour=view["period"].dt.hour).pivot_table(index="date", columns="hour", values="demand_mwh", aggfunc="mean")
heat_fig = px.imshow(heat, aspect="auto", labels={"x": "Hour UTC", "y": "Date", "color": "Demand (MWh)"})
st.plotly_chart(heat_fig, use_container_width=True)
st.markdown("**What this shows:** recurring intraday patterns, unusual peak windows, and days that depart from the typical shape become much easier to spot than in a raw hourly table.")

st.subheader("Operational stress signal")
stress_fig = px.area(view, x="period", y="stress_score", labels={"stress_score": "Stress screening score"}, range_y=[0, 100])
stress_fig.add_hline(y=65, line_dash="dash", annotation_text="High-screening threshold")
st.plotly_chart(stress_fig, use_container_width=True)
st.markdown("**What this shows:** this is a transparent screening signal combining demand level, forecast error, ramping, and interchange dependence. It is not an EIA/NERC reliability rating and does not predict blackouts.")

left, right = st.columns(2)
with left:
    st.subheader("Net generation and interchange")
    gen_cols = [c for c in ["net_generation_mwh", "total_interchange_mwh"] if c in view]
    if gen_cols:
        long = view.melt(id_vars="period", value_vars=gen_cols, var_name="series", value_name="mwh")
        gen_fig = px.line(long, x="period", y="mwh", color="series", labels={"mwh": "MWh", "series": "Series"})
        st.plotly_chart(gen_fig, use_container_width=True)
    st.markdown("**What this shows:** the dashboard keeps local generation and interchange visible so high-demand periods can be viewed in the context of how the system is being supplied.")

with right:
    st.subheader("Highest-stress hours")
    cols = [c for c in ["period", "demand_mwh", "abs_forecast_error_mwh", "demand_ramp_pct", "total_interchange_mwh", "stress_score", "stress_band"] if c in view]
    events = view.nlargest(10, "stress_score")[cols]
    st.dataframe(events, use_container_width=True, hide_index=True)
    st.markdown("**What this shows:** the event table turns the composite signal back into inspectable operating evidence so a reviewer can see *why* an hour was flagged.")

st.caption(f"Data source mode: {source_label}. EIA production ingestion uses API v2 / electricity / rto / region-data.")
