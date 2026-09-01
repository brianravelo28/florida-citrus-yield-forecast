# Data Schema Documentation

Complete schema definitions for all data pipeline stages.

## 1. Input: USDA NASS Yield Data

**Source**: USDA NASS QuickStats API  
**File**: `data/nass_yield.csv`  
**Records**: 35 (1990–2024)

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| `county_name` | string | "Polk County" | Florida county name |
| `year` | int | 1990 | Calendar year |
| `yield_lbs_acre` | float | 45993.43 | Citrus yield in lbs/acre |
| `data_source` | string | "NASS" | Data origin (NASS or SYNTHETIC) |

### SQL-like DDL
```sql
CREATE TABLE nass_yield (
  county_name VARCHAR(50),
  year INT,
  yield_lbs_acre FLOAT,
  data_source VARCHAR(20)
);
```

### Statistics (Polk County, 1990–2024)
| Stat | Value |
|------|-------|
| Count | 35 |
| Mean | 37,235 lbs/acre |
| Std Dev | 5,148 lbs/acre |
| Min | 28,326 lbs/acre (2023) |
| Max | 46,723 lbs/acre (1993) |
| Trend | -34% (1990–2024) |

---

## 2. Input: NOAA Weather Data

**Source**: NOAA CDO v1 API  
**File**: `data/noaa_weather.csv`  
**Records**: 5,040 (4 stations × 12 months × 35 years)

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| `station_id` | string | "USW00012834" | NOAA station code |
| `station_name` | string | "Lakeland Linder" | Station name |
| `date` | date | "1990-01-15" | Observation date (monthly agg) |
| `datatype` | string | "TMAX" | TMAX, TMIN, or PRCP |
| `value` | float | 859.0 | Encoded value (see notes) |
| `data_source` | string | "NOAA" | Data origin (NOAA or SYNTHETIC) |

### Value Encoding
- **TMAX/TMIN**: Temperature in °F × 10 (859 = 85.9°F)
- **PRCP**: Precipitation in mm × 10 (60 = 6.0 mm)

### Stations (Polk County, FL)
| Station | Code | Location | Elevation |
|---------|------|----------|-----------|
| Lakeland Linder | USW00012834 | Lakeland, FL | 155 ft |
| Tampa International | USW00012842 | Tampa, FL | 26 ft |
| Orlando Executive | USW00013880 | Orlando, FL | 95 ft |
| Sebring | USW00014907 | Sebring, FL | 28 ft |

---

## 3. Engineered Features (Model Data)

**Source**: `src/feature_engineering.py`  
**File**: `data/df_model.csv`  
**Records**: 35 (one per year)

### Feature List (13 Total)

| # | Feature | Type | Units | Calculation | Seasonal Window |
|---|---------|------|-------|-------------|-----------------|
| 1 | `frost_days_bloom` | int | days | Count(TMIN ≤ 32°F) | Jan–Mar |
| 2 | `tmax_mean_grow` | float | °F | Mean(TMAX) | May–Aug |
| 3 | `tmin_mean_grow` | float | °F | Mean(TMIN) | May–Aug |
| 4 | `precip_total_grow` | float | mm | Sum(PRCP) | May–Aug |
| 5 | `precip_rolling_30` | float | mm | Max 30-day window | May–Aug |
| 6 | `precip_rolling_60` | float | mm | Max 60-day window | May–Aug |
| 7 | `precip_rolling_90` | float | mm | Max 90-day window | May–Aug |
| 8 | `temp_variance_grow` | float | °F | Std(TMAX) | May–Aug |
| 9 | `gdd_total_grow` | float | °F-days | Sum(max(0, (TMAX+TMIN)/2 - 50)) | May–Aug |
| 10 | `precip_deviation` | float | mm | precip_total_grow - 30yr_mean | May–Aug |
| 11 | `yield_lag1` | float | lbs/acre | Prior year yield | (t-1) |
| 12 | `year_numeric` | int | year | Calendar year | N/A |
| 13 | `log_yield` | float | log(lbs/acre) | log(yield_lbs_acre + 1) | Target |

### Full DataFrame Schema
```
county_name                  object
year                          int64
yield_lbs_acre             float64   ← Target (raw)
tmax_mean_grow             float64
tmin_mean_grow             float64
frost_days_bloom             int64
precip_total_grow          float64
precip_rolling_30          float64
precip_rolling_60          float64
precip_rolling_90          float64
temp_variance_grow         float64
gdd_total_grow             float64
precip_deviation           float64
yield_lag1                 float64
year_numeric                 int64
log_yield                  float64   ← Target (log-transformed)
```

### Example Row (1990)
```
county_name: Polk County
year: 1990
yield_lbs_acre: 45993.43
tmax_mean_grow: 81.36
tmin_mean_grow: 65.69
frost_days_bloom: 0
precip_total_grow: 1.775
precip_rolling_30: NaN (insufficient history)
precip_rolling_60: NaN
precip_rolling_90: NaN
temp_variance_grow: 3.24
gdd_total_grow: 94.11
precip_deviation: 0.072
yield_lag1: NaN (no prior year)
year_numeric: 1990
log_yield: 10.74
```

---

## 4. Output: Model Results

**Source**: `src/train_models.py`  
**File**: `results/model_results.json`

### JSON Structure
```json
{
  "arima": {
    "model_name": "ARIMA(1,1,1)",
    "rmse": 2104.90,
    "mae": 1683.93,
    "forecast_2023": 31272.62,
    "forecast_2024": 31224.10
  },
  "lightgbm": {
    "model_name": "LightGBM",
    "rmse": 3500.0,
    "mae": 2800.0,
    "feature_importance": {
      "frost_days_bloom": 450.2,
      "gdd_total_grow": 380.5,
      "tmax_mean_grow": 275.3,
      "precip_total_grow": 200.1,
      "yield_lag1": 150.0
    },
    "top_features": [
      "frost_days_bloom",
      "gdd_total_grow",
      "tmax_mean_grow",
      "precip_total_grow",
      "yield_lag1"
    ],
    "forecast_2023": 29500.0,
    "forecast_2024": 30800.0
  }
}
```

---

## 5. Output: Stress Indicator

**Source**: `src/stress_indicator.py`  
**File**: `results/stress_indicator.csv`  
**Records**: 35 (one per year)

### Additional Columns (Beyond df_model)
| Column | Type | Range | Notes |
|--------|------|-------|-------|
| `stress_score` | float | 0.0–2.0 | Composite stress indicator |
| `stress_level` | string | LOW\|MODERATE\|HIGH | Risk category |

### Stress Score Calculation
```
stress_score = (
    0.4 × (frost_days / percentile_75_historical) +
    0.3 × (abs(precip_deviation) / historical_std) +
    0.2 × (historical_gdd_mean / gdd_current) +
    0.1 × (1 if yield_lag1 < percentile_25 else 0)
)
```

### Categories
| Category | Score Range | Interpretation |
|----------|-------------|-----------------|
| LOW | 0.0–0.5 | Favorable conditions, yield risk minimal |
| MODERATE | 0.5–1.0 | Caution advised, monitor crop stress |
| HIGH | > 1.0 | Severe stress, significant yield loss risk |

### Example Rows
```
year,stress_score,stress_level
1990,0.15,LOW
2022,0.72,MODERATE
2024,0.35,LOW
```

---

## 6. Dashboard Data (Real-Time)

**Source**: Loaded from CSV files via Dash callbacks  
**Format**: Plotly Graph Objects (JSON)

### Tab 1: Overview
```python
{
  "yield_forecast": Scatter(x=years, y=yield_lbs_acre),
  "stress_timeline": Scatter(x=years, y=stress_score, color=stress_level),
  "kpi_current_yield": 31645,
  "kpi_forecast_2025": 31224,
  "kpi_stress_level": "LOW"
}
```

### Tab 2: Weather
```python
{
  "temperature_series": [
    Scatter(x=years, y=tmax_mean_grow, name="Max Temp"),
    Scatter(x=years, y=tmin_mean_grow, name="Min Temp")
  ],
  "feature_importance": Bar(x=features, y=importance)
}
```

### Tab 3: Scenarios
```python
{
  "scenario_yield": [baseline_yield, scenario_yield],
  "economic_impact": {
    "baseline_revenue": 50000 * 0.45 * 31645,
    "scenario_revenue": 50000 * 0.45 * 28000,
    "loss": "$ millions"
  }
}
```

---

## Data Quality Notes

### Missing Values
- **Yield**: None (all years present)
- **Weather**: First year has NaN for lag features (expected)
- **Rolling windows**: First 90 days have NaN (insufficient history)

### Handling Strategy
```python
# Feature engineering:
df = df.dropna(subset=['log_yield', 'frost_days_bloom'])  # Drop first row

# Model training:
X_train = X_train[df['year'] <= 2022]  # Use only years with full data
```

### Data Validation
✅ No negative yields  
✅ No negative frost days (count only)  
✅ No temperature outliers (>120°F or <-10°F)  
✅ No precipitation spikes (>1000 mm/month)  
✅ Year range: 1990–2024 (complete)  

---

## Reproducibility

### Exact Calculations
All feature calculations use **daily weather data**, aggregated as follows:

```python
# Frost days (bloom season)
bloom_period = weather[(month >= 1) & (month <= 3)]
frost_days = len(bloom_period[tmin_f <= 32])

# Growing season aggregates
grow_period = weather[(month >= 5) & (month <= 8)]
tmax_mean = grow_period['tmax_f'].mean()
gdd = sum(max(0, (tmax_f + tmin_f) / 2 - 50) for each day in grow_period)
```

### Software Versions
```
Python: 3.9+
pandas: 1.3+
numpy: 1.21+
statsmodels: 0.13+ (ARIMA)
lightgbm: 3.3+ (GBM)
```

---

## References

- USDA NASS QuickStats: https://quickstats.nass.usda.gov/
- NOAA CDO API: https://www.ncei.noaa.gov/access/services/data/v1
- Growing Degree Days (GDD): https://en.wikipedia.org/wiki/Growing_degree-day (base 50°F for citrus)
