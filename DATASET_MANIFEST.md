# GridPulse Dataset Manifest

This manifest records the exact EIA-930 six-month BALANCE files used for the current PJM 2022–2025 analysis. The raw files are intentionally not committed to Git because of their size.

## Source snapshot

| File | Size | SHA-256 |
|---|---:|---|
| `EIA930_BALANCE_2022_Jan_Jun.csv` | 40.6 MB | `d3d315a0c29d9527a1c64cf6ddcdcc5c0b7281fddd99199bd70f06d242e503d5` |
| `EIA930_BALANCE_2022_Jul_Dec.csv` | 40.9 MB | `267575c29ef40f386bcf3bc3993013b9ce13a3a154b89b702559a75dd742976d` |
| `EIA930_BALANCE_2023_Jan_Jun.csv` | 40.0 MB | `a0e14e9c07ab4cc1de3e384c7be890b0c61d9de3fe04ad3ae5ec739f1f35ec1b` |
| `EIA930_BALANCE_2023_Jul_Dec.csv` | 40.6 MB | `c719fc1b513eec8982ce209b6e3173fc64b2d0d243f83d3bf0d8d1adf6222de2` |
| `EIA930_BALANCE_2024_Jan_Jun.csv` | 39.8 MB | `26768c495c3ba987e29d79df2e40d4e741f9dbcff086f53c12ff774465756a10` |
| `EIA930_BALANCE_2024_Jul_Dec.csv` | 45.7 MB | `a602a8e577cfdd2fa3083413eaa4dd8ba7f0d2b26a2986f8f6d22917465ea49f` |
| `EIA930_BALANCE_2025_Jan_Jun.csv` | 45.4 MB | `fac4bb991dfa1dab3b4b35300ccab54ac99be13a40ce91954db8ddafb2816242` |
| `EIA930_BALANCE_2025_Jul_Dec.csv` | 46.0 MB | `1146158b972439db7c7f4cc7d0491e07644ddbf244d03b8ecb44cb2c833d10f1` |

## PJM analytical coverage

- Balancing authority: **PJM**
- Region label in source: **MIDA**
- Hourly rows after filtering: **35,064**
- UTC coverage: **2022-01-01 06:00 UTC through 2026-01-01 05:00 UTC**
- Local-calendar coverage: **January 1, 2022 through December 31, 2025**
- Duplicate UTC timestamps: **0**
- Missing UTC hour slots: **0**
- Missing adjusted demand rows: **3**
- Missing net-generation rows: **3**
- Missing day-ahead forecast rows: **121**
- Missing total-interchange rows: **120**
- Demand hours using EIA imputation/adjustment fields: **117**
- Net-generation hours using EIA imputation/adjustment fields: **117**

## Schema note

The source schema changes in 2024 H2. Earlier files expose combined hydro/pumped-storage, solar, and wind fields. Later files split several of those categories and add storage-related columns.

GridPulse does not concatenate those columns naively. `src/gridpulse/balance.py` normalizes the two schemas into stable analytical fuel categories and preserves the source filename on each hourly operating record.

## QA note

A one-hour demand discontinuity on 2024-11-21 at 12:00 PM PJM local time is retained as a source-data QA event rather than silently corrected. The adjusted demand value is 56,260 MW between adjacent observations near 95,000 MW, while reported net generation remains near 98,000 MW.

## Reproduce

Place the files above under `data/raw/eia930/` and run:

```bash
python scripts/prepare_downloaded_eia.py \
  --balance-source data/raw/eia930 \
  --respondent PJM \
  --output-dir data/processed
```

The preparation step emits the normalized hourly/fuel Parquet tables and a machine-readable QA summary.
