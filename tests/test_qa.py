import pandas as pd

from gridpulse.features import add_qa_flags


def test_qa_flags_isolated_demand_discontinuity_without_mutation():
    periods = pd.date_range("2024-11-21 15:00", periods=3, freq="h", tz="UTC")
    demand = [94_800.0, 56_300.0, 95_500.0]
    df = pd.DataFrame(
        {
            "period": periods,
            "respondent": "PJM",
            "demand_mw": demand,
            "net_generation_mw": [98_000.0, 98_100.0, 98_200.0],
            "total_interchange_mw": [3_000.0, 3_100.0, 3_000.0],
        }
    )
    out = add_qa_flags(df)
    assert out["demand_mw"].tolist() == demand
    assert out.loc[1, "qa_anomaly"]
    assert not out.loc[2, "qa_anomaly"]
    assert "isolated one-hour demand discontinuity" in out.loc[1, "qa_anomaly_reason"]
