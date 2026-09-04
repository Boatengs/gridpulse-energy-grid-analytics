import pandas as pd
from gridpulse.features import add_operational_features


def test_operational_features_use_mw_and_balance_residual():
    df = pd.DataFrame(
        {
            "period": pd.date_range("2025-01-01", periods=3, freq="h", tz="UTC"),
            "respondent": ["PJM"] * 3,
            "demand_mw": [100.0, 110.0, 121.0],
            "forecast_mw": [98.0, 108.0, 120.0],
            "net_generation_mw": [105.0, 116.0, 125.0],
            "total_interchange_mw": [5.0, 6.0, 4.0],
        }
    )
    out = add_operational_features(df)
    assert "forecast_error_mw" in out
    assert out.loc[1, "forecast_error_mw"] == 2
    assert abs(out.loc[1, "demand_ramp_pct"] - 10) < 1e-9
    assert out["balance_residual_mw"].abs().max() == 0
