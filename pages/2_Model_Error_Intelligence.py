from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="GridPulse Model Error Intelligence", page_icon="📊", layout="wide")

RESULT_DIR = Path("results/error_slices")
SUMMARY_PATH = RESULT_DIR / "summary.json"
TABLE_PATHS = {
    "Hour of day": RESULT_DIR / "hour.csv",
    "Month": RESULT_DIR / "month.csv",
    "Season": RESULT_DIR / "season.csv",
    "Weekday vs weekend": RESULT_DIR / "day_type.csv",
    "Demand decile": RESULT_DIR / "demand_decile.csv",
}


@st.cache_data(show_spinner=False)
def load_summary(path: str) -> dict:
    return json.loads(Path(path).read_text())


@st.cache_data(show_spinner=False)
def load_table(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def format_gain(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:.1f}%"


def format_mw(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{value:,.0f} MW"


def improvement_chart(table: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=table["slice"].astype(str),
            y=table["improvement_pct"],
            name="ML improvement vs EIA",
            customdata=table[["eia_mae_mw", "ml_mae_mw", "rows"]],
            hovertemplate=(
                "%{x}<br>Improvement: %{y:.1f}%<br>"
                "EIA MAE: %{customdata[0]:,.0f} MW<br>"
                "ML MAE: %{customdata[1]:,.0f} MW<br>"
                "Rows: %{customdata[2]:,.0f}<extra></extra>"
            ),
        )
    )
    fig.add_hline(y=0, line_dash="dash", annotation_text="No improvement")
    fig.update_layout(
        title=title,
        height=380,
        yaxis_title="MAE improvement vs EIA (%)",
        xaxis_title=None,
        margin={"l": 20, "r": 20, "t": 55, "b": 35},
    )
    return fig


def mae_chart(table: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    x = table["slice"].astype(str)
    fig.add_trace(go.Bar(x=x, y=table["eia_mae_mw"], name="EIA day-ahead MAE"))
    fig.add_trace(go.Bar(x=x, y=table["ml_mae_mw"], name="GridPulse ML MAE"))
    fig.update_layout(
        title=title,
        barmode="group",
        height=390,
        yaxis_title="MAE (MW)",
        xaxis_title=None,
        margin={"l": 20, "r": 20, "t": 55, "b": 35},
        legend={"orientation": "h", "y": 1.10},
    )
    return fig


def bias_chart(table: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    x = table["slice"].astype(str)
    fig.add_trace(go.Scatter(x=x, y=table["eia_bias_mw"], mode="lines+markers", name="EIA bias"))
    fig.add_trace(go.Scatter(x=x, y=table["ml_bias_mw"], mode="lines+markers", name="GridPulse ML bias"))
    fig.add_hline(y=0, line_dash="dash")
    fig.update_layout(
        title=title,
        height=350,
        yaxis_title="Mean actual − forecast (MW)",
        xaxis_title=None,
        margin={"l": 20, "r": 20, "t": 55, "b": 35},
        legend={"orientation": "h", "y": 1.10},
    )
    return fig


st.title("📊 Model Error Intelligence")
st.caption(
    "Where the validated 2025 GridPulse residual-correction model gains or loses advantage relative to "
    "EIA's reported day-ahead forecast. All comparisons use common rows with complete actual, EIA, and ML values."
)

if not SUMMARY_PATH.exists() or not all(path.exists() for path in TABLE_PATHS.values()):
    st.warning(
        "Verified error-slice result files are not present in this checkout yet. "
        "Run `python scripts/generate_error_slices.py` against the prepared frozen PJM dataset, "
        "or use the committed result files once available."
    )
    st.stop()

summary = load_summary(str(SUMMARY_PATH))
tables = {label: load_table(str(path)) for label, path in TABLE_PATHS.items()}

headline = summary.get("headline_gate", {})
rolling_context = (
    "This page is a diagnostic decomposition of the same 2025 holdout model that cleared the EIA promotion gate. "
    "Slice results do not replace the headline common-row benchmark or rolling-origin validation."
)
st.info(rolling_context)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Common 2025 rows", f"{summary.get('common_rows', 0):,}")
m2.metric("Overall MAE gain vs EIA", format_gain(headline.get("overall_improvement_pct")))
m3.metric("Peak MAE gain vs EIA", format_gain(headline.get("peak_improvement_pct")))
d10 = summary.get("highest_demand_decile", {})
m4.metric("Highest-demand decile gain", format_gain(d10.get("improvement_pct")))

st.subheader("Where does the advantage widen or narrow?")
summary_rows = []
summary_key_map = {
    "hour": "Hour of day",
    "month": "Month",
    "season": "Season",
    "day_type": "Weekday vs weekend",
    "demand_decile": "Demand decile",
}
for key, label in summary_key_map.items():
    item = summary.get(key, {})
    weakest = item.get("weakest") or {}
    strongest = item.get("strongest") or {}
    summary_rows.append(
        {
            "Dimension": label,
            "Weakest slice": weakest.get("slice", "N/A"),
            "Weakest gain": format_gain(weakest.get("improvement_pct")),
            "Strongest slice": strongest.get("slice", "N/A"),
            "Strongest gain": format_gain(strongest.get("improvement_pct")),
        }
    )
st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

selected_dimension = st.selectbox("Explore a slice dimension", list(TABLE_PATHS.keys()))
selected_table = tables[selected_dimension]

left, right = st.columns(2)
with left:
    st.plotly_chart(
        improvement_chart(selected_table, f"{selected_dimension}: ML improvement vs EIA"),
        use_container_width=True,
        config={"displaylogo": False},
    )
with right:
    st.plotly_chart(
        mae_chart(selected_table, f"{selected_dimension}: absolute forecast error"),
        use_container_width=True,
        config={"displaylogo": False},
    )

st.plotly_chart(
    bias_chart(selected_table, f"{selected_dimension}: signed forecast bias"),
    use_container_width=True,
    config={"displaylogo": False},
)

st.subheader("Underforecast behavior")
under = selected_table[[
    "slice",
    "rows",
    "eia_underforecast_rate_pct",
    "ml_underforecast_rate_pct",
]].copy()
under = under.rename(
    columns={
        "slice": "Slice",
        "rows": "Rows",
        "eia_underforecast_rate_pct": "EIA underforecast rate (%)",
        "ml_underforecast_rate_pct": "ML underforecast rate (%)",
    }
)
st.dataframe(under, use_container_width=True, hide_index=True)
st.caption(
    "Underforecast rate is the share of hours where actual demand exceeded the forecast. "
    "A lower MAE does not necessarily imply a lower underforecast frequency, so GridPulse reports both."
)

st.subheader("Highest-demand decile")
if d10:
    a, b, c, d = st.columns(4)
    a.metric("EIA MAE", format_mw(d10.get("eia_mae_mw")))
    b.metric("GridPulse ML MAE", format_mw(d10.get("ml_mae_mw")))
    c.metric("Improvement", format_gain(d10.get("improvement_pct")))
    d.metric("Rows", f"{d10.get('rows', 0):,}")

st.warning(
    "These slices describe the frozen PJM 2025 holdout only. They do not establish the same pattern for other "
    "balancing authorities, future years, revised EIA snapshots, or a different forecast-issuance clock."
)
