"""Shared visual presentation helpers for GridPulse Streamlit dashboards."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

TEXT = "#0F172A"
MUTED = "#475569"
CYAN = "#0284C7"
GREEN = "#059669"
AMBER = "#D97706"
ROSE = "#E11D48"
GRID = "rgba(15, 23, 42, 0.10)"
AXIS = "rgba(15, 23, 42, 0.28)"
PLOT_BG = "#FFFFFF"
PAPER_BG = "#FFFFFF"


def configure_plotly_theme() -> None:
    """Install and activate a high-contrast Plotly theme for the white UI."""
    pio.templates["gridpulse_light"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor=PAPER_BG,
            plot_bgcolor=PLOT_BG,
            font={"color": TEXT, "family": "Inter, ui-sans-serif, system-ui, sans-serif", "size": 13},
            title={"font": {"color": TEXT, "size": 18}},
            legend={
                "font": {"color": TEXT},
                "bgcolor": "rgba(255,255,255,.94)",
                "bordercolor": "rgba(15,23,42,.12)",
                "borderwidth": 1,
            },
            hoverlabel={"bgcolor": "#FFFFFF", "bordercolor": CYAN, "font": {"color": TEXT}},
            annotationdefaults={"font": {"color": TEXT}},
            colorway=[CYAN, AMBER, GREEN, ROSE, "#7C3AED", "#0891B2", "#DB2777", "#EA580C"],
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
    pio.templates.default = "gridpulse_light"


def inject_dashboard_css() -> None:
    """Apply a clean white presentation surface with strong text contrast."""
    configure_plotly_theme()
    st.markdown(
        f"""
        <style>
        :root {{ color-scheme: light; }}
        html, body, [data-testid="stAppViewContainer"], .stApp {{
          background: #FFFFFF !important;
          color: {TEXT} !important;
        }}
        header[data-testid="stHeader"] {{
          background: #FFFFFF !important;
          border-bottom: 1px solid rgba(15,23,42,.06);
        }}
        .stApp, .stApp p, .stApp span, .stApp label,
        [data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"],
        [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{ color: {TEXT}; }}
        [data-testid="stCaptionContainer"] {{ color: {MUTED} !important; }}
        section[data-testid="stSidebar"] {{
          background: #FFFFFF !important;
          border-right: 1px solid rgba(15,23,42,.08);
        }}
        section[data-testid="stSidebar"] * {{ color: {TEXT}; }}
        div[data-testid="stMetric"] {{
          background: #FFFFFF;
          border: 1px solid rgba(15,23,42,.10);
          border-radius: 16px;
          padding: .8rem .9rem;
          box-shadow: 0 8px 24px rgba(15,23,42,.06);
          animation: gp-rise .52s ease both;
        }}
        div[data-testid="stMetric"]:hover {{
          border-color: rgba(2,132,199,.32);
          box-shadow: 0 12px 28px rgba(15,23,42,.09);
          transform: translateY(-1px);
          transition: all .18s ease;
        }}
        div[data-testid="stMetricLabel"] {{ color: {MUTED} !important; }}
        div[data-testid="stMetricValue"] {{ color: {TEXT} !important; }}
        div[data-testid="stDataFrame"], div[data-testid="stPlotlyChart"] {{
          background: #FFFFFF !important;
          border-radius: 14px;
          overflow: hidden;
        }}
        div[data-baseweb="select"], div[data-baseweb="input"],
        div[data-baseweb="popover"], div[data-baseweb="menu"] {{
          background: #FFFFFF !important;
        }}
        div[data-baseweb="select"] *, div[data-baseweb="input"] *,
        div[data-baseweb="popover"] *, div[data-baseweb="menu"] *,
        div[data-testid="stWidgetLabel"] * {{ color: {TEXT} !important; }}
        input, textarea {{
          background: #FFFFFF !important;
          color: {TEXT} !important;
          border-color: rgba(15,23,42,.16) !important;
        }}
        button {{ color: {TEXT} !important; }}
        button[kind="primary"], button[kind="secondary"] {{
          border-color: rgba(2,132,199,.24) !important;
          background: #FFFFFF !important;
        }}
        h1, h2, h3 {{ color: {TEXT} !important; letter-spacing: -.018em; }}
        h1 {{ animation: gp-title .7s cubic-bezier(.2,.7,.2,1) both; }}
        hr {{ border-color: rgba(15,23,42,.10); }}
        .gp-presentation-strip {{
          height: 3px;
          width: 100%;
          margin: .15rem 0 1rem;
          border-radius: 999px;
          background: linear-gradient(90deg, transparent, {CYAN}, {GREEN}, transparent);
          background-size: 220% 100%;
          animation: gp-scan 3.6s linear infinite;
          box-shadow: 0 0 12px rgba(2,132,199,.14);
        }}
        .gp-live-pulse {{
          display:inline-block; width:.58rem; height:.58rem; border-radius:50%;
          background:{GREEN}; box-shadow:0 0 0 0 rgba(5,150,105,.32);
          animation: gp-pulse 1.8s ease-out infinite;
        }}
        @keyframes gp-title {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
        @keyframes gp-rise {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
        @keyframes gp-scan {{ 0% {{ background-position:220% 0; }} 100% {{ background-position:-20% 0; }} }}
        @keyframes gp-pulse {{ 0% {{ box-shadow:0 0 0 0 rgba(5,150,105,.32); }} 70% {{ box-shadow:0 0 0 10px rgba(5,150,105,0); }} 100% {{ box-shadow:0 0 0 0 rgba(5,150,105,0); }} }}
        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{ animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; }}
        }}
        </style>
        <div class="gp-presentation-strip"></div>
        """,
        unsafe_allow_html=True,
    )
