from __future__ import annotations

import os
from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from gridpulse.demo import make_demo_data
from gridpulse.eia import EIAClient
from gridpulse.features import add_operational_features
from gridpulse.stress import add_stress_score

st.set_page_config(page_title="GridPulse", page_icon="⚡", layout="wide")
load_dotenv()

st.title("GridPulse — Energy Demand & Grid Stress Analytics")
st.caption("Live EIA-930 API • demand • forecast error • ramping • generation • interchange • stress screening")


def _configured_api_key() -> str | None:
    """Read the EIA key from Streamlit secrets first, then the local environment."""
    try:
        secret_key = st.secrets.get("EIA_API_KEY")
    except Exception:
        secret_key = None
    env_key = os.getenv("EIA_API_KEY")
    key = secret_key or env_key
    if not key or key == "replace_me":
        return None
    return str(key)


@st.cache_data(ttl=3600, show_spinner=False)
def load_live_grid_data(api_key: str, respondent: str, start: str, end: str) -> pd.DataFrame:
    """Query EIA directly and keep the result in Streamlit's cache instead of a CSV."""
    raw = EIAClient(api_key=api_key).region_data(
        respondent=respondent,
        start=start,
        end=end,
    )
    if raw.empty:
        return raw
    return add_stress_score(add_operational_features(raw))


api_key = _configured_api_key()
default_respondent = os.getenv("GRIDPULSE_RESPONDENT", "PJM")
default_end = date.today() - timedelta(days=1)
default_start = default_end - timedelta(days=13)

with st.sidebar:
    st.header("Live EIA query")
    respondent = st.text_input("Balancing authority code", value=default_respondent).strip().upper()
    selected_dates = st.date_input(
        "Analysis window",
        value=(default_start, default_end),
        max_value=date.today(),
    )
    st.caption("Live API responses are cached for one hour. No CSV is required for dashboard use.")

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
else:
    start_date = end_date = selected_dates

start = f"{start_date.isoformat()}T00"
end = f"{end_date.isoformat()}T23"

demo_mode = False
source_label = ""

if api_key and respondent:
    try:
        with st.spinner("Querying EIA-930 directly…"):
            df = load_live_grid_data(api_key, respondent, start, end)
        if df.empty:
            raise ValueError("EIA returned no rows for this balancing authority and date window.")
        source_label = f"Live EIA-930 API · {respondent} · {start_date} to {end_date}"
    except Exception as exc:
        st.error(f"Live EIA request failed: {exc}")
        st.info("Showing the synthetic development fixture so the dashboard remains reviewable.")
        df = add_stress_score(add_operational_features(make_demo_data()))
        source_label = "Synthetic fallback after live API failure"
        demo_mode = True
else:
    df = add_stress_score(add_operational_features(make_demo_data()))
    source_label = "Synthetic development fixture — configure EIA_API_KEY for live data"
    demo_mode = True

if "stress_score" not in df.columns:
    df = add_stress_score(add_operational_features(df))

df["period"] = pd.to_datetime(df["period"], utc=True)

if demo_mode:
    st.warning(
        "Demo mode: these values are synthetic and only exercise the analytical/dashboard pipeline. "
        "They are not EIA findings."
    )
else:
    st.success(f"Loaded {len(df):,} hourly rows directly from {source_label}.")

respondents = sorted(df.get("respondent", pd.Series([respondent or "DEMO"])).dropna().astype(str).unique())
selected = st.sidebar.selectbox("Loaded balancing authority / region", respondents)
subset = df[df.get("respondent", selected).astype(str) == selected].copy()

max_hours = max(1, len(subset))
default_hours = min(24 * 14, max_hours)
min_hours = min(24, max_hours)
if max_hours > min_hours:
    window = st.sidebar.slider("Hours to display", min_hours, max_hours, default_hours, step=min(24, max_hours - min_hours))
else:
    window = max_hours
view = subset.tail(window).copy()

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
    events = view.nlargest(min(10, len(view)), "stress_score")[cols]
    st.dataframe(events, use_container_width=True, hide_index=True)
    st.markdown("**What this shows:** the event table turns the composite signal back into inspectable operating evidence so a reviewer can see *why* an hour was flagged.")

st.caption(f"Data source mode: {source_label}. Production dashboard data is queried directly from EIA API v2 and cached in memory.")
