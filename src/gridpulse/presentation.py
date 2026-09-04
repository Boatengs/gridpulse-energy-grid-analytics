"""Shared visual presentation helpers for GridPulse Streamlit dashboards."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

TEXT = "#EAF6FF"
MUTED = "#9FB3C8"
CYAN = "#38BDF8"
GREEN = "#34D399"
AMBER = "#FBBF24"
ROSE = "#FB7185"
GRID = "rgba(148, 163, 184, 0.16)"
AXIS = "rgba(148, 163, 184, 0.42)"
PLOT_BG = "rgba(7, 16, 24, 0.72)"
PAPER_BG = "rgba(0, 0, 0, 0)"


def configure_plotly_theme() -> None:
    """Install and activate a high-contrast Plotly theme for the dark UI."""
    pio.templates["gridpulse_dark"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=PAPER_BG,
            plot_bgcolor=PLOT_BG,
            font={"color": TEXT, "family": "Inter, ui-sans-serif, system-ui, sans-serif", "size": 13},
            title={"font": {"color": TEXT, "size": 18}},
            legend={
                "font": {"color": TEXT},
                "bgcolor": "rgba(7,16,24,.72)",
                "bordercolor": "rgba(148,163,184,.18)",
                "borderwidth": 1,
            },
            hoverlabel={"bgcolor": "#0E1B24", "bordercolor": CYAN, "font": {"color": TEXT}},
            annotationdefaults={"font": {"color": TEXT}},
            colorway=[CYAN, AMBER, GREEN, ROSE, "#A78BFA", "#22D3EE", "#F472B6", "#F59E0B"],
            xaxis={
                "color": TEXT,
                "tickfont": {"color": TEXT},
                "title": {"font": {"color": TEXT}},
                "gridcolor": GRID,
                "zerolinecolor": AXIS,
                "linecolor": AXIS,
                "automargin": True,
            },
            yaxis={
                "color": TEXT,
                "tickfont": {"color": TEXT},
                "title": {"font": {"color": TEXT}},
                "gridcolor": GRID,
                "zerolinecolor": AXIS,
                "linecolor": AXIS,
                "automargin": True,
            },
            coloraxis={
                "colorbar": {
                    "tickfont": {"color": TEXT},
                    "title": {"font": {"color": TEXT}},
                }
            },
        )
    )
    pio.templates.default = "gridpulse_dark"


def inject_dashboard_css() -> None:
    """Apply accessible dark-mode contrast plus lightweight presentation motion."""
    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: dark; }}
        .stApp {{
          background:
            radial-gradient(circle at 15% 0%, rgba(56,189,248,.09), transparent 31rem),
            radial-gradient(circle at 92% 18%, rgba(52,211,153,.055), transparent 28rem),
            #071018;
        }}
        .stApp, .stApp p, .stApp span, .stApp label,
        [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{ color: {TEXT}; }}
        [data-testid="stCaptionContainer"] {{ color: {MUTED}; }}
        section[data-testid="stSidebar"] {{
          background: linear-gradient(180deg, rgba(14,27,36,.98), rgba(7,16,24,.98));
          border-right: 1px solid rgba(148,163,184,.12);
        }}
        div[data-testid="stMetric"] {{
          background: linear-gradient(145deg, rgba(14,27,36,.88), rgba(7,16,24,.68));
          border: 1px solid rgba(56,189,248,.18);
          border-radius: 16px;
          padding: .8rem .9rem;
          box-shadow: 0 10px 30px rgba(0,0,0,.18), inset 0 1px rgba(255,255,255,.025);
          animation: gp-rise .52s ease both;
        }}
        div[data-testid="stMetric"]:hover {{
          border-color: rgba(56,189,248,.42);
          box-shadow: 0 12px 34px rgba(0,0,0,.25), 0 0 24px rgba(56,189,248,.07);
          transform: translateY(-1px);
          transition: all .18s ease;
        }}
        div[data-testid="stMetricLabel"] {{ color: {MUTED} !important; }}
        div[data-testid="stMetricValue"] {{ color: {TEXT} !important; }}
        div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {{
          border-radius: 14px;
          overflow: hidden;
        }}
        div[data-baseweb="select"] *, div[data-baseweb="input"] *,
        div[data-baseweb="popover"] *, div[data-testid="stWidgetLabel"] * {{ color: {TEXT} !important; }}
        button[kind="primary"], button[kind="secondary"] {{
          border-color: rgba(56,189,248,.28) !important;
        }}
        h1, h2, h3 {{ color: {TEXT}; letter-spacing: -.018em; }}
        h1 {{ animation: gp-title .7s cubic-bezier(.2,.7,.2,1) both; }}
        hr {{ border-color: rgba(148,163,184,.14); }}
        .gp-presentation-strip {{
          height: 3px;
          width: 100%;
          margin: .15rem 0 1rem;
          border-radius: 999px;
          background: linear-gradient(90deg, transparent, {CYAN}, {GREEN}, transparent);
          background-size: 220% 100%;
          animation: gp-scan 3.6s linear infinite;
          box-shadow: 0 0 18px rgba(56,189,248,.22);
        }}
        .gp-live-pulse {{
          display:inline-block; width:.58rem; height:.58rem; border-radius:50%;
          background:{GREEN}; box-shadow:0 0 0 0 rgba(52,211,153,.5);
          animation: gp-pulse 1.8s ease-out infinite;
        }}
        @keyframes gp-title {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
        @keyframes gp-rise {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
        @keyframes gp-scan {{ 0% {{ background-position:220% 0; }} 100% {{ background-position:-20% 0; }} }}
        @keyframes gp-pulse {{ 0% {{ box-shadow:0 0 0 0 rgba(52,211,153,.42); }} 70% {{ box-shadow:0 0 0 10px rgba(52,211,153,0); }} 100% {{ box-shadow:0 0 0 0 rgba(52,211,153,0); }} }}
        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{ animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; }}
        }}
        </style>
        <div class="gp-presentation-strip"></div>
        """,
        unsafe_allow_html=True,
    )
