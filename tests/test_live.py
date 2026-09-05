from __future__ import annotations

import pandas as pd
import pytest

from gridpulse.live import build_replay_figure, replay_window, telemetry_snapshot


def sample_frame(rows: int = 10) -> pd.DataFrame:
    periods = pd.date_range("2025-01-01", periods=rows, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "period": periods,
            "demand_mw": [100_000 + i * 100 for i in range(rows)],
            "forecast_mw": [99_500 + i * 90 for i in range(rows)],
            "forecast_error_mw": [500 + i * 10 for i in range(rows)],
            "demand_ramp_pct": [0.1] * rows,
            "stress_score": [40 + i for i in range(rows)],
            "net_generation_mw": [102_000 + i * 100 for i in range(rows)],
            "total_interchange_mw": [2_000.0] * rows,
        }
    )


def test_replay_window_sorts_and_bounds_rows() -> None:
    frame = sample_frame(12).iloc[::-1]
    result = replay_window(frame, max_rows=5)
    assert len(result) == 5
    assert result["period"].is_monotonic_increasing
    assert result["period"].iloc[0] == pd.Timestamp("2025-01-01 07:00:00+00:00")


def test_replay_window_rejects_nonpositive_limit() -> None:
    with pytest.raises(ValueError):
        replay_window(sample_frame(), max_rows=0)


def test_telemetry_snapshot_marks_frozen_data_as_replay() -> None:
    snap = telemetry_snapshot(
        sample_frame(3),
        now=pd.Timestamp("2025-01-02 00:00:00+00:00"),
        live_mode=False,
    )
    assert snap["freshness"] == "Replay"
    assert snap["demand_mw"] == 100_200.0


def test_telemetry_snapshot_classifies_live_freshness() -> None:
    frame = sample_frame(1)
    fresh = telemetry_snapshot(
        frame,
        now=pd.Timestamp("2025-01-01 03:00:00+00:00"),
        live_mode=True,
    )
    stale = telemetry_snapshot(
        frame,
        now=pd.Timestamp("2025-01-02 00:00:00+00:00"),
        live_mode=True,
    )
    assert fresh["freshness"] == "Fresh"
    assert stale["freshness"] == "Stale"


def test_build_replay_figure_has_synchronized_browser_animation() -> None:
    fig = build_replay_figure(sample_frame(8), max_frames=8, frame_ms=100)
    assert len(fig.data) == 5
    assert len(fig.frames) == 6
    assert fig.layout.updatemenus[0].buttons[0].label == "▶ Play"
    assert fig.layout.updatemenus[0].buttons[2].label == "↺ Restart"
    assert len(fig.layout.sliders[0].steps) == 6
    assert fig.layout.yaxis2.range == (0, 100)


def test_build_replay_figure_keeps_light_theme_labels_visible() -> None:
    fig = build_replay_figure(sample_frame(8), max_frames=8, frame_ms=100)
    theme = fig.layout.template.layout
    assert theme.font.color == "#0F172A"
    assert theme.xaxis.tickfont.color == "#0F172A"
    assert theme.yaxis.tickfont.color == "#0F172A"


def test_build_replay_figure_rejects_extreme_speed() -> None:
    with pytest.raises(ValueError):
        build_replay_figure(sample_frame(), frame_ms=5)
