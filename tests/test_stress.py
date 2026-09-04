import numpy as np
import pandas as pd

from gridpulse.demo import make_demo_data
from gridpulse.features import add_operational_features
from gridpulse.stress import add_stress_score


def test_stress_score_is_bounded_and_labeled():
    df = add_stress_score(add_operational_features(make_demo_data(hours=120)))
    valid = df["stress_score"].dropna()
    assert valid.between(0, 100).all()
    assert set(df["stress_band"].dropna().unique()).issubset(
        {"normal", "elevated", "high", "very_high"}
    )


def test_missing_component_is_reweighted_not_treated_as_zero():
    df = pd.DataFrame(
        {
            "demand_percentile": [1.0, 1.0],
            "forecast_error_percentile": [1.0, 1.0],
            "demand_ramp_pct": [10.0, 10.0],
            "interchange_percentile": [1.0, np.nan],
        }
    )
    out = add_stress_score(df)
    assert out.loc[0, "stress_score"] == 100
    assert out.loc[1, "stress_score"] == 100
    assert out.loc[1, "stress_components_available"] == 3
