from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from gridpulse.demo import make_demo_data
from gridpulse.eia import EIAClient
from gridpulse.features import add_operational_features, add_qa_flags
from gridpulse.live import build_replay_figure, replay_window, telemetry_snapshot
from gridpulse.stress import add_stress_score

st.set_page_config(page_title="GridPulse Live Control Room", page_icon="⚡", layout="wide")
load_dotenv()

PROCESSED_HOURLY = Path(
    os.getenv("GRIDPULSE_HOURLY_PATH", "data/processed/gridpulse_hourly.parquet")
)
RESULT_SUMMARY = Path("results/model_evaluation_summary.json")
RESULT_BENCHMARK = Path("results/headline_benchmark.csv")

st.markdown(
    """
    <style>
    .gp-status {display:inline-flex;align-items:center;gap:.45rem;padding:.28rem .65rem;
      border:1px solid rgba(125,211,252,.35);border-radius:999px;font-size:.82rem;font-weight:700;}
    .gp-dot {width:.58rem;height:.58rem;border-radius:50%;display:inline-block;background:#38bdf8;
      box-shadow:0 0 0 .18rem rgba(56,189,248,.12);}
    .gp-dot.live {background:#34d399;box-shadow:0 0 0 .18rem rgba(52,211,153,.12);}
    .gp-dot.warn {background:#fbbf24;box-shadow:0 0 0 .18rem rgba(251,191,36,.12);}
    .gp-dot.stale {background:#fb7185;box-shadow:0 0 0 .18rem rgba(251,113,133,.12);}
    .gp-hero {padding:.9rem 0 .35rem 0;}
    .gp-hero h1 {margin-bottom:.25rem;}
    .gp-kicker {letter-spacing:.12em;text-transform:uppercase;font-size:.76rem;font-weight:800;opacity:.7;}
    div[data-testid="stMetric"] {border:1px solid rgba(148,163,184,.18);border-radius:.8rem;padding:.7rem .85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def configured_api_key() -> str | None:
    try:
        secret_key = st.secrets.get("EIA_API_KEY")
    except Exception:
        secret_key = None
    key = secret_key or os.getenv("EIA_API_KEY")
    return None if not key or str(key) == "replace_me" else str(key)


@st.cache_data(show_spinner=False)
def load_frozen(path: str) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    return frame.dropna(subset=["period"]).sort_values("period").reset_index(drop=True)


@st.cache_data(ttl=240, show_spinner=False)
def load_live(api_key: str, respondent: str, start: str, end: str) -> pd.DataFrame:
    raw = EIAClient(api_key=api_key).region_data(
        respondent=respondent,
        start=start,
        end=end,
    )
    if raw.empty:
        return raw
    return add_qa_flags(add_stress_score(add_operational_features(raw)))


@st.cache_data(show_spinner=False)
def load_validation_result() -> tuple[dict, pd.DataFrame]:
    summary = json.loads(RESULT_SUMMARY.read_text()) if RESULT_SUMMARY.exists() else {}
    benchmark = pd.read_csv(RESULT_BENCHMARK) if RESULT_BENCHMARK.exists() else pd.DataFrame()
    return summary, benchmark


def prepare_demo() -> pd.DataFrame:
    return add_qa_flags(add_stress_score(add_operational_features(make_demo_data())))


def fmt(value: float | None, suffix: str = "", decimals: int = 0) -> str:
    if value is None or not np.isfinite(value):
        return "N/A"
    return f"{value:,.{decimals}f}{suffix}"


def status_html(snapshot: dict) -> str:
    status = str(snapshot.get("freshness", "No data"))
    cls = "live" if status == "Fresh" else "warn" if status in {"Replay", "Delayed"} else "stale"
    latest = snapshot.get("latest_period")
    latest_text = "no timestamp" if latest is None else pd.Timestamp(latest).strftime("%Y-%m-%d %H:%M UTC")
    age = snapshot.get("age_hours")
    age_text = "" if age is None else f" · {age:.1f}h old"
    return (
        f'<span class="gp-status"><span class="gp-dot {cls}"></span>'
        f'{status} · {latest_text}{age_text}</span>'
    )


def stress_gauge(score: float | None) -> go.Figure:
    value = 0.0 if score is None or not np.isfinite(score) else float(np.clip(score, 0, 100))
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": "/100"},
            title={"text": "Operational stress screen"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"thickness": 0.28},
                "steps": [
                    {"range": [0, 40], "color": "rgba(52,211,153,.12)"},
                    {"range": [40, 65], "color": "rgba(251,191,36,.12)"},
                    {"range": [65, 100], "color": "rgba(251,113,133,.12)"},
                ],
                "threshold": {"line": {"width": 3}, "thickness": 0.75, "value": 65},
            },
        )
    )
    fig.update_layout(height=280, margin={"l": 30, "r": 30, "t": 55, "b": 15})
    return fig


st.markdown('<div class="gp-hero"><div class="gp-kicker">GridPulse live operations</div></div>', unsafe_allow_html=True)
st.title("⚡ Live Animated Control Room")
st.caption(
    "PJM/EIA-930 hourly operations with browser-side replay animation and optional auto-refresh. "
    "EIA-930 is an hourly operational feed, not sub-second telemetry, and observations can arrive late or be revised."
)

api_key = configured_api_key()
with st.sidebar:
    st.header("Control room")
    source = st.radio(
        "Feed mode",
        ["Frozen PJM replay", "Live EIA API", "Synthetic demo"],
        index=0,
    )
    respondent = st.text_input("Balancing authority", value="PJM").strip().upper()
    replay_hours = st.slider("Replay window (hours)", 24, 336, 168, step=24)
    speed_label = st.select_slider(
        "Playback speed",
        options=["Slow", "Normal", "Fast", "Very fast"],
        value="Normal",
    )
    speed_ms = {"Slow": 360, "Normal": 180, "Fast": 90, "Very fast": 45}[speed_label]
    auto_refresh = st.toggle(
        "Auto-refresh live feed",
        value=True,
        disabled=source != "Live EIA API",
        help="When enabled, the live API panel reruns about every five minutes.",
    )

summary, benchmark = load_validation_result()
headline_gate = summary.get("headline_gate", {}) if isinstance(summary, dict) else {}
rolling = summary.get("rolling_origin", {}) if isinstance(summary, dict) else {}
if headline_gate.get("passes"):
    st.info(
        "Validated 2025 benchmark: GridPulse ML reduced overall MAE by "
        f"**{headline_gate.get('overall_improvement_pct', 0):.1f}%** and peak-demand MAE by "
        f"**{headline_gate.get('peak_improvement_pct', 0):.1f}%** vs EIA; "
        f"it beat EIA in **{rolling.get('folds_beating_eia', 0)}/{rolling.get('valid_folds', 0)}** rolling folds. "
        "This is historical validation, not a guarantee for incoming live hours."
    )


def render_control_room(frame: pd.DataFrame, *, live_mode: bool, label: str) -> None:
    if frame.empty:
        st.error("No operating rows are available for this control-room view.")
        return

    frame = frame.copy()
    frame["period"] = pd.to_datetime(frame["period"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["period"]).sort_values("period")
    if "stress_score" not in frame.columns:
        frame = add_stress_score(add_operational_features(frame))
    if "qa_anomaly" not in frame.columns:
        frame = add_qa_flags(frame)

    view = replay_window(frame, max_rows=replay_hours)
    snap = telemetry_snapshot(view, live_mode=live_mode)
    st.markdown(status_html(snap), unsafe_allow_html=True)
    st.caption(f"{label} · {snap.get('freshness_detail', '')}")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Demand", fmt(snap.get("demand_mw"), " MW"))
    c2.metric("EIA forecast", fmt(snap.get("forecast_mw"), " MW"))
    c3.metric("Forecast error", fmt(snap.get("forecast_error_mw"), " MW"))
    c4.metric("Hourly ramp", fmt(snap.get("demand_ramp_pct"), "%", 1))
    c5.metric("Stress screen", fmt(snap.get("stress_score"), "/100"))

    left, right = st.columns([2.2, 1])
    with left:
        st.subheader("Animated operating replay")
        replay = build_replay_figure(view, max_frames=replay_hours, frame_ms=speed_ms)
        st.plotly_chart(replay, use_container_width=True, config={"displaylogo": False})
        st.caption(
            "Press Play to replay the operating window hour by hour. The animation is browser-side, "
            "so playback stays smooth without repeatedly querying EIA."
        )
    with right:
        st.plotly_chart(stress_gauge(snap.get("stress_score")), use_container_width=True, config={"displaylogo": False})
        st.metric("Net generation", fmt(snap.get("net_generation_mw"), " MW"))
        st.metric("Total interchange", fmt(snap.get("total_interchange_mw"), " MW"))

    st.subheader("Live pulse tape")
    tape = view.tail(min(36, len(view))).copy()
    tape_fig = go.Figure()
    tape_fig.add_trace(
        go.Scatter(
            x=tape["period"],
            y=tape["demand_mw"],
            mode="lines+markers",
            name="Demand",
            line={"width": 3},
        )
    )
    tape_fig.add_trace(
        go.Scatter(
            x=tape["period"],
            y=tape["forecast_mw"],
            mode="lines",
            name="EIA forecast",
            line={"width": 2, "dash": "dot"},
        )
    )
    tape_fig.update_layout(
        height=310,
        hovermode="x unified",
        yaxis_title="MW",
        xaxis_title=None,
        margin={"l": 15, "r": 15, "t": 20, "b": 15},
        legend={"orientation": "h", "y": 1.12},
    )
    st.plotly_chart(tape_fig, use_container_width=True, config={"displaylogo": False})

    left, right = st.columns(2)
    with left:
        st.subheader("Recent operating events")
        event_cols = [
            c
            for c in [
                "period",
                "demand_mw",
                "forecast_error_mw",
                "demand_ramp_pct",
                "stress_score",
                "stress_band",
            ]
            if c in view.columns
        ]
        events = view.nlargest(min(8, len(view)), "stress_score")[event_cols]
        st.dataframe(events, use_container_width=True, hide_index=True)
    with right:
        st.subheader("QA watch")
        if "qa_anomaly" in view.columns and view["qa_anomaly"].fillna(False).any():
            qa_cols = [
                c
                for c in [
                    "period",
                    "demand_mw",
                    "net_generation_mw",
                    "qa_anomaly_reason",
                ]
                if c in view.columns
            ]
            st.dataframe(
                view[view["qa_anomaly"].fillna(False)][qa_cols].tail(8),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No GridPulse QA anomaly flags in the displayed window.")

    st.warning(
        "The stress score is a transparent screening indicator, not an official EIA/NERC reliability rating "
        "and not a blackout-prediction signal."
    )


if source == "Frozen PJM replay":
    if PROCESSED_HOURLY.exists():
        frozen = load_frozen(str(PROCESSED_HOURLY))
        subset = frozen[frozen["respondent"].astype(str).eq(respondent)].copy()
        if subset.empty:
            st.error(f"No frozen rows found for {respondent}.")
        else:
            render_control_room(subset, live_mode=False, label=f"Frozen EIA-930 · {respondent}")
    else:
        st.warning("Prepared EIA Parquet is unavailable here, so the page is using the synthetic demo fixture.")
        render_control_room(prepare_demo(), live_mode=False, label="Synthetic fallback")

elif source == "Synthetic demo":
    render_control_room(prepare_demo(), live_mode=False, label="Synthetic development fixture")

else:
    if not api_key:
        st.error(
            "Live EIA mode needs EIA_API_KEY in Streamlit secrets or the environment. "
            "The frozen replay remains fully usable without credentials."
        )
    elif not respondent:
        st.error("Enter a balancing-authority code such as PJM.")
    else:
        def current_query_window() -> tuple[str, str]:
            now = pd.Timestamp.now(tz="UTC").floor("h")
            start = now - pd.Timedelta(hours=max(replay_hours + 48, 96))
            return start.strftime("%Y-%m-%dT%H"), now.strftime("%Y-%m-%dT%H")

        def draw_live_once() -> None:
            start, end = current_query_window()
            try:
                live = load_live(api_key, respondent, start, end)
            except Exception as exc:
                st.error(f"EIA API request failed: {exc}")
                return
            render_control_room(live, live_mode=True, label=f"Live EIA-930 API · {respondent}")

        @st.fragment(run_every="5m")
        def draw_live_auto() -> None:
            draw_live_once()

        if auto_refresh:
            draw_live_auto()
        else:
            draw_live_once()

st.caption(
    "Live mode refreshes the EIA API on a short cadence; the animated replay itself is local to your browser. "
    "Raw downloaded data remain outside Git."
)
