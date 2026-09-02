from gridpulse.demo import make_demo_data
from gridpulse.features import add_operational_features
from gridpulse.stress import add_stress_score


def test_stress_score_is_bounded_and_labeled():
    df = add_stress_score(add_operational_features(make_demo_data(hours=120)))
    assert df["stress_score"].between(0, 100).all()
    assert set(df["stress_band"].unique()).issubset({"normal", "elevated", "high", "very_high"})
