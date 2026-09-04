import pandas as pd

from gridpulse.balance import load_balance_exports


def test_balance_loader_filters_pjm_and_normalizes_schema_change(tmp_path):
    legacy = pd.DataFrame({
        "Balancing Authority": ["PJM", "OTHER"],
        "UTC Time at End of Hour": ["01/01/2024 1:00:00 AM", "01/01/2024 1:00:00 AM"],
        "Local Time at End of Hour": ["12/31/2023 8:00:00 PM", "12/31/2023 8:00:00 PM"],
        "Hour Number": [1, 1],
        "Demand Forecast (MW)": [100, 10],
        "Demand (MW) (Adjusted)": [105, 10],
        "Net Generation (MW) (Adjusted)": [110, 10],
        "Total Interchange (MW) (Adjusted)": [5, 0],
        "Demand (MW) (Imputed)": [None, None],
        "Net Generation (MW) (Imputed)": [None, None],
        "Total Interchange (MW) (Imputed)": [None, None],
        "Net Generation (MW) from Coal (Adjusted)": [20, 2],
        "Net Generation (MW) from Natural Gas (Adjusted)": [30, 3],
        "Net Generation (MW) from Nuclear (Adjusted)": [40, 4],
        "Net Generation (MW) from All Petroleum Products (Adjusted)": [1, 0],
        "Net Generation (MW) from Hydropower and Pumped Storage (Adjusted)": [5, 0],
        "Net Generation (MW) from Solar (Adjusted)": [4, 0],
        "Net Generation (MW) from Wind (Adjusted)": [8, 1],
        "Net Generation (MW) from Other Fuel Sources (Adjusted)": [2, 0],
        "Net Generation (MW) from Unknown Fuel Sources (Adjusted)": [0, 0],
        "Region": ["MIDA", "X"],
    })
    modern = pd.DataFrame({
        "Balancing Authority": ["PJM"],
        "UTC Time at End of Hour": ["07/01/2024 5:00:00 AM"],
        "Local Time at End of Hour": ["07/01/2024 1:00:00 AM"],
        "Hour Number": [1],
        "Demand Forecast (MW)": [120],
        "Demand (MW) (Adjusted)": [123],
        "Net Generation (MW) (Adjusted)": [126],
        "Total Interchange (MW) (Adjusted)": [3],
        "Demand (MW) (Imputed)": [None],
        "Net Generation (MW) (Imputed)": [None],
        "Total Interchange (MW) (Imputed)": [None],
        "Net Generation (MW) from Coal (Adjusted)": [21],
        "Net Generation (MW) from Natural Gas (Adjusted)": [35],
        "Net Generation (MW) from Nuclear (Adjusted)": [42],
        "Net Generation (MW) from All Petroleum Products (Adjusted)": [1],
        "Net Generation (MW) from Hydropower Excluding Pumped Storage (Adjusted)": [6],
        "Net Generation (MW) from Pumped Storage  (Adjusted)": [1],
        "Net Generation (MW) from Solar without Integrated Battery Storage (Adjusted)": [5],
        "Net Generation (MW) from Wind without Integrated Battery Storage (Adjusted)": [9],
        "Net Generation (MW) from Other Fuel Sources (Adjusted)": [2],
        "Net Generation (MW) from Unknown Fuel Sources (Adjusted)": [0],
        "Region": ["MIDA"],
    })
    legacy.to_csv(tmp_path / "legacy.csv", index=False)
    modern.to_csv(tmp_path / "modern.csv", index=False)

    hourly, fuel = load_balance_exports(tmp_path, respondent="PJM")

    assert len(hourly) == 2
    assert set(hourly["respondent"]) == {"PJM"}
    assert list(hourly["demand_mw"]) == [105, 123]
    modern_fuel = fuel[fuel["period"] == pd.Timestamp("2024-07-01 05:00:00+00:00")]
    assert modern_fuel.loc[modern_fuel["fuel_type"] == "hydro_pumped", "generation_mw"].iloc[0] == 7
    assert modern_fuel.loc[modern_fuel["fuel_type"] == "solar", "generation_mw"].iloc[0] == 5
