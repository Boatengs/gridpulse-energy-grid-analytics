"""GridPulse analytical package."""

from .features import add_operational_features
from .presentation import configure_plotly_theme
from .stress import add_stress_score

# Every Streamlit surface imports at least one GridPulse module. Configure Plotly
# once at package import so axes, legends, annotations, hover labels, and colorbars
# remain readable against the dark dashboard background.
configure_plotly_theme()

__all__ = ["add_operational_features", "add_stress_score"]
