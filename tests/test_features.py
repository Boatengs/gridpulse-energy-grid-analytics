from gridpulse.demo import make_demo_data
from gridpulse.features import add_operational_features


def test_operational_features_are_created():
    df = add_operational_features(make_demo_data(hours=72))
    expected = {"demand_ramp_pct", "demand_percentile", "forecast_error_mwh", "abs_forecast_error_pct", "interchange_share"}
    assert expected.issubset(df.columns)
    assert df["demand_percentile"].between(0, 1).all()
