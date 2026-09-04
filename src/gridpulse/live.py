"""Helpers for GridPulse live/replay dashboard surfaces."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def replay_window(frame: pd.DataFrame, max_rows: int = 168) -> pd.DataFrame:
    """Return a chronological, bounded replay window without mutating source data."""
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")
    if frame.empty:
        return frame.copy()
    if "period" not in frame.columns:
        raise ValueError("frame must contain a period column")
    out = frame.copy()
    out["period"] = pd.to_datetime(out["period"], utc=True, errors="coerce")
    out = out.dropna(subset=["period"]).sort_values("period")
    return out.tail(max_rows).reset_index(drop=True)


def telemetry_snapshot(
    frame: pd.DataFrame,
    *,
    now: pd.Timestamp | None = None,
    live_mode: bool = False,
) -> dict[str, Any]:
    """Summarize the latest operating row and classify data freshness."""
    if frame.empty:
        return {
            "latest_period": None,
            "age_hours": None,
            "freshness": "No data",
            "freshness_detail": "No operating rows are available.",
        }

    work = replay_window(frame, max_rows=max(1, len(frame)))
    if work.empty:
        return {
            "latest_period": None,
            "age_hours": None,
            "freshness": "No data",
            "freshness_detail": "No valid timestamps are available.",
        }

    row = work.iloc[-1]
    latest = pd.Timestamp(row["period"])
    current = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    if current.tzinfo is None:
        current = current.tz_localize("UTC")
    else:
        current = current.tz_convert("UTC")
    age_hours = max(0.0, (current - latest).total_seconds() / 3600.0)

    if not live_mode:
        freshness = "Replay"
        detail = "Historical/frozen data replay; not a live telemetry feed."
    elif age_hours <= 4:
        freshness = "Fresh"
        detail = "Latest EIA hourly observation is within four hours of current UTC time."
    elif age_hours <= 12:
        freshness = "Delayed"
        detail = "EIA hourly observations are arriving with a visible delay."
    else:
        freshness = "Stale"
        detail = "Latest EIA observation is more than twelve hours old."

    def value(name: str) -> float | None:
        if name not in row.index or pd.isna(row[name]):
            return None
        return float(row[name])

    return {
        "latest_period": latest,
        "age_hours": age_hours,
        "freshness": freshness,
        "freshness_detail": detail,
        "demand_mw": value("demand_mw"),
        "forecast_mw": value("forecast_mw"),
        "forecast_error_mw": value("forecast_error_mw"),
        "demand_ramp_pct": value("demand_ramp_pct"),
        "stress_score": value("stress_score"),
        "net_generation_mw": value("net_generation_mw"),
        "total_interchange_mw": value("total_interchange_mw"),
    }


def build_replay_figure(
    frame: pd.DataFrame,
    *,
    max_frames: int = 168,
    frame_ms: int = 120,
) -> go.Figure:
    """Build a browser-side synchronized operating replay with play/pause controls.

    The upper panel progressively reveals actual demand and EIA's day-ahead forecast.
    The lower panel tracks the GridPulse stress screen on the same time axis. A timeline
    slider lets a reviewer scrub hour-by-hour, matching the presentation style used for
    animated portfolio dashboards while keeping the underlying source rows unchanged.
    """
    if frame_ms < 20 or frame_ms > 2000:
        raise ValueError("frame_ms must be between 20 and 2000 milliseconds")
    work = replay_window(frame, max_rows=max_frames)
    required = {"period", "demand_mw", "forecast_mw"}
    missing = required.difference(work.columns)
    if missing:
        raise ValueError(f"frame is missing required columns: {sorted(missing)}")

    if work.empty:
        fig = go.Figure()
        fig.update_layout(
            height=500,
            xaxis_title=None,
            yaxis_title="MW",
            annotations=[
                {
                    "text": "No valid operating rows available for replay.",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                }
            ],
        )
        return fig

    periods = work["period"].tolist()
    demand = pd.to_numeric(work["demand_mw"], errors="coerce").tolist()
    forecast = pd.to_numeric(work["forecast_mw"], errors="coerce").tolist()
    if "stress_score" in work.columns:
        stress = pd.to_numeric(work["stress_score"], errors="coerce").tolist()
    else:
        stress = [None] * len(work)

    finite_mw = pd.concat(
        [
            pd.to_numeric(work["demand_mw"], errors="coerce"),
            pd.to_numeric(work["forecast_mw"], errors="coerce"),
        ],
        ignore_index=True,
    ).dropna()
    if finite_mw.empty:
        mw_range = None
    else:
        lo = float(finite_mw.min())
        hi = float(finite_mw.max())
        pad = max((hi - lo) * 0.08, max(abs(hi), 1.0) * 0.02)
        mw_range = [lo - pad, hi + pad]

    def traces(end: int) -> list[go.Scatter]:
        current_period = periods[end - 1]
        current_demand = demand[end - 1]
        current_stress = stress[end - 1]
        return [
            go.Scatter(
                x=periods[:end],
                y=demand[:end],
                name="Actual demand",
                mode="lines",
                line={"width": 3, "color": "#38BDF8"},
                fill="tozeroy",
                fillcolor="rgba(56,189,248,.055)",
                hovertemplate="%{x|%b %d %H:%M}<br>Demand %{y:,.0f} MW<extra></extra>",
            ),
            go.Scatter(
                x=periods[:end],
                y=forecast[:end],
                name="EIA day-ahead forecast",
                mode="lines",
                line={"width": 2.4, "dash": "dot", "color": "#FBBF24"},
                hovertemplate="%{x|%b %d %H:%M}<br>EIA forecast %{y:,.0f} MW<extra></extra>",
            ),
            go.Scatter(
                x=[current_period],
                y=[current_demand],
                name="Current demand",
                mode="markers",
                marker={
                    "size": 13,
                    "color": "#EAF6FF",
                    "line": {"width": 3, "color": "#38BDF8"},
                },
                showlegend=False,
                hovertemplate="Current hour<br>%{x|%Y-%m-%d %H:%M UTC}<br>%{y:,.0f} MW<extra></extra>",
            ),
            go.Scatter(
                x=periods[:end],
                y=stress[:end],
                name="Stress screen",
                mode="lines",
                line={"width": 2.4, "color": "#FB7185"},
                fill="tozeroy",
                fillcolor="rgba(251,113,133,.10)",
                hovertemplate="%{x|%b %d %H:%M}<br>Stress %{y:.0f}/100<extra></extra>",
            ),
            go.Scatter(
                x=[current_period],
                y=[current_stress],
                name="Current stress",
                mode="markers",
                marker={"size": 10, "color": "#FB7185", "line": {"width": 2, "color": "#EAF6FF"}},
                showlegend=False,
                hovertemplate="Current stress %{y:.0f}/100<extra></extra>",
            ),
        ]

    initial_end = min(2, len(work))
    initial = traces(initial_end)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.08,
        subplot_titles=("Demand vs EIA forecast", "Operational stress screen"),
    )
    for idx, trace in enumerate(initial):
        fig.add_trace(trace, row=1 if idx < 3 else 2, col=1)

    frames: list[go.Frame] = []
    for i in range(initial_end, len(work)):
        frame_traces = traces(i + 1)
        frames.append(
            go.Frame(
                name=str(i),
                data=frame_traces,
                traces=[0, 1, 2, 3, 4],
            )
        )
    fig.frames = frames

    slider_steps = []
    for i in range(initial_end, len(work)):
        label = pd.Timestamp(periods[i]).strftime("%b %d %H:%M")
        slider_steps.append(
            {
                "label": label,
                "method": "animate",
                "args": [
                    [str(i)],
                    {
                        "frame": {"duration": 0, "redraw": True},
                        "transition": {"duration": 0},
                        "mode": "immediate",
                    },
                ],
            }
        )

    fig.update_layout(
        height=590,
        hovermode="x unified",
        margin={"l": 28, "r": 20, "t": 72, "b": 105},
        legend={"orientation": "h", "y": 1.11, "x": 0},
        transition={"duration": min(120, frame_ms)},
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0,
                "y": 1.22,
                "showactive": False,
                "pad": {"r": 8, "t": 0},
                "buttons": [
                    {
                        "label": "▶ Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {"duration": frame_ms, "redraw": True},
                                "transition": {"duration": min(100, frame_ms)},
                                "fromcurrent": True,
                                "mode": "immediate",
                            },
                        ],
                    },
                    {
                        "label": "⏸ Pause",
                        "method": "animate",
                        "args": [
                            [None],
                            {
                                "frame": {"duration": 0, "redraw": False},
                                "transition": {"duration": 0},
                                "mode": "immediate",
                            },
                        ],
                    },
                    {
                        "label": "↺ Restart",
                        "method": "animate",
                        "args": [
                            [str(initial_end)],
                            {
                                "frame": {"duration": 0, "redraw": True},
                                "transition": {"duration": 0},
                                "mode": "immediate",
                            },
                        ],
                    },
                ],
            }
        ],
        sliders=[
            {
                "active": 0,
                "currentvalue": {"prefix": "Replay hour · ", "font": {"size": 12}},
                "pad": {"t": 34, "b": 0},
                "len": 0.98,
                "x": 0.01,
                "steps": slider_steps,
            }
        ] if slider_steps else [],
    )
    fig.update_xaxes(
        title_text=None,
        range=[periods[0], periods[-1]],
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikedash="dot",
        spikecolor="rgba(234,246,255,.45)",
    )
    fig.update_yaxes(title_text="MW", range=mw_range, row=1, col=1)
    fig.update_yaxes(title_text="Score", range=[0, 100], dtick=25, row=2, col=1)
    fig.add_hline(
        y=65,
        line_dash="dash",
        line_color="rgba(251,113,133,.55)",
        annotation_text="High-screening threshold",
        annotation_position="top right",
        row=2,
        col=1,
    )
    return fig
