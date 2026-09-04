"""Helpers for GridPulse live/replay dashboard surfaces."""
from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go


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
    """Build a browser-side cumulative demand/forecast replay with play/pause controls."""
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
            height=430,
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
    demand = work["demand_mw"].tolist()
    forecast = work["forecast_mw"].tolist()

    def traces(end: int) -> list[go.Scatter]:
        return [
            go.Scatter(
                x=periods[:end],
                y=demand[:end],
                name="Actual demand",
                mode="lines",
                line={"width": 3},
            ),
            go.Scatter(
                x=periods[:end],
                y=forecast[:end],
                name="EIA day-ahead forecast",
                mode="lines",
                line={"width": 2, "dash": "dot"},
            ),
            go.Scatter(
                x=[periods[end - 1]],
                y=[demand[end - 1]],
                name="Current demand",
                mode="markers",
                marker={"size": 10},
                showlegend=False,
            ),
        ]

    initial_end = min(2, len(work))
    fig = go.Figure(data=traces(initial_end))
    fig.frames = [
        go.Frame(name=str(i), data=traces(i + 1))
        for i in range(initial_end, len(work))
    ]

    fig.update_layout(
        height=430,
        yaxis_title="MW",
        xaxis_title=None,
        hovermode="x unified",
        margin={"l": 20, "r": 20, "t": 30, "b": 20},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        updatemenus=[
            {
                "type": "buttons",
                "direction": "left",
                "x": 0,
                "y": 1.20,
                "showactive": False,
                "buttons": [
                    {
                        "label": "▶ Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "frame": {"duration": frame_ms, "redraw": True},
                                "transition": {"duration": 0},
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
                ],
            }
        ],
    )
    return fig
