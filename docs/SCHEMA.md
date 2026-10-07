# Data Schema

All files are CSV/JSON in `data/` and `results/`. Temperatures are degrees F; raw precipitation is inches; engineered precipitation features are millimetres (inches x 25.4).

## Raw data

### `data/nass_yield.csv` - 35 rows (1990-2024)

| Column | Description |
|---|---|
| `county_name` | Always `Florida (Statewide)` (county yield is not published) |
| `year` | Calendar year |
| `yield_lbs_acre` | NASS `BOXES / ACRE` x 90 lb/box |
| `data_source` | `NASS` |

### `data/noaa_weather.csv` - 106,289 rows

One row per station, day, and variable.

| Column | Description |
|---|---|
| `station_id`, `station_name` | GHCND station (Lakeland Linder, Tampa International, Orlando Executive, Sebring) |
| `date` | `YYYY-MM-DD` |
| `datatype` | `TMAX`, `TMIN` (F) or `PRCP` (inches) |
| `value` | Observation, after the plausibility filter |
| `data_source` | `NOAA` |

### `data/county_acreage.csv` - 20 rows

| Column | Description |
|---|---|
| `county_name` | Polk, Hendry, DeSoto, Highlands |
| `year` | Census year: 2002, 2007, 2012, 2017, 2022 |
| `bearing_acres` | Orange bearing acres, all varieties combined (USDA Census of Agriculture). **Blank when USDA withheld the total** |
| `status` | `published` (16 rows) or `withheld` (4 rows: Hendry 2002 and 2007, DeSoto 2012, Highlands 2022). `withheld` means the Census marked the total `(D)`: withheld to avoid disclosing individual operations' data |
| `data_source` | `NASS_CENSUS` |

Withheld values are never estimated. For those four rows USDA still published one single variety, which is not a county total and is not used (Hendry 2002 and 2007 and Highlands 2022: Valencia only; DeSoto 2012: Mid & Navel only).

### `data/county_weather.csv` - 281,383 rows

Same layout as `noaa_weather.csv`, plus a leading `county_name` column (7 columns).

## Engineered data

### `data/df_model.csv` - 35 rows x 16 columns

| Column | Description |
|---|---|
| `county_name`, `year`, `yield_lbs_acre` | Key and raw yield |
| `tmax_mean_grow`, `tmin_mean_grow` | Mean daily max/min temperature, May-Aug (F) |
| `frost_days_bloom` | Days with TMIN <= 32 F, Jan-Mar |
| `precip_total_grow` | Total precipitation, May-Aug (mm) |
| `precip_rolling_30`, `_60`, `_90` | Largest 30/60/90-observation-day precipitation sum within May-Aug (mm) |
| `temp_variance_grow` | Std. dev. of daily max temperature, May-Aug (F) |
| `gdd_total_grow` | Sum of max(0, (TMAX+TMIN)/2 - 50), May-Aug |
| `precip_deviation` | `precip_total_grow` minus its 1990-2024 mean (mm) |
| `yield_lag1` | Previous year's yield (NaN for 1990) |
| `year_numeric` | Calendar year |
| `log_yield` | `log(1 + yield_lbs_acre)` (model target) |

### `data/county_features.csv` - 140 rows (4 counties x 35 years) x 14 columns

`county_name`, `year`, the same weather features as above (without lag/trend/target columns; `precip_deviation` is relative to that county's own 1990-2024 mean), `bearing_acres` (populated only for published Census totals; blank for withheld totals and for non-Census years - never interpolated), and `acreage_status` (`published`, `withheld`, or blank for non-Census years, so withheld values can be told apart from years with no Census). Too few observation days exist for the rolling windows in two county-years, so `precip_rolling_60` is NaN for DeSoto 1993 and `precip_rolling_90` is NaN for DeSoto 1993 and Hendry 2021.

## Results

### `results/model_results.json`

```
arima:    model_name, rmse, mae, forecast_2023, forecast_2024
lightgbm: model_name, rmse, mae, forecast_2023, forecast_2024,
          feature_importance {feature: split count}, top_features [5 names]
```

Forecasts are the two holdout-year predictions (2023, 2024); no later year is predicted.

### `results/stress_indicator.csv` - 35 rows x 18 columns

All `df_model.csv` columns plus `stress_score` (float) and `stress_level` (`LOW`, `MODERATE`, `HIGH`).
