# Florida Citrus Yield Forecasting System

**A data-driven ML pipeline for predicting citrus yields using USDA NASS crop data and NOAA weather patterns.**

## Project Overview

This system forecasts Florida citrus yields (Polk County, 1990–2024) using:
- **Historical yield data** from USDA NASS (1990–2024)
- **Weather data** from NOAA (temperature, precipitation, frost days)
- **13 engineered features** capturing seasonal agricultural stress
- **Two forecasting models**: ARIMA baseline + LightGBM with walk-forward cross-validation
- **Climate stress indicators** showing yield risk by year
- **Interactive Plotly Dash dashboard** with 3 analytical tabs

## Data Pipeline

### 1. Data Fetching (`src/fetch_data.py`)
- Fetches citrus yield data from USDA NASS QuickStats API
- Fetches weather data (TMAX, TMIN, PRCP) from NOAA CDO v1 API
- Saves to `data/nass_yield.csv` and `data/noaa_weather.csv`

**Output:**
- `data/nass_yield.csv`: Yield records (year, county, lbs/acre)
- `data/noaa_weather.csv`: Daily weather observations (station, date, temp, precip)

### 2. Feature Engineering (`src/feature_engineering.py`)
Aggregates weather by year and calculates:

| Feature | Definition | Agricultural Meaning |
|---------|-----------|----------------------|
| `frost_days_bloom` | Days ≤32°F in Jan–Mar | Freeze damage risk during citrus bloom |
| `tmax_mean_grow` | Mean max temp, May–Aug | Growing season heat |
| `tmin_mean_grow` | Mean min temp, May–Aug | Growing season cold stress |
| `precip_total_grow` | Total precipitation, May–Aug | Water availability in growth |
| `precip_rolling_30/60/90` | Max rolling windows (mm) | Peak rainfall intensity & duration |
| `temp_variance_grow` | Std dev of max temps | Thermal stability (lower = better) |
| `gdd_total_grow` | Growing degree days (base 50°F) | Ripening accumulation |
| `precip_deviation` | Deviation from 30-yr mean | Drought/wet signal |
| `yield_lag1` | Prior year yield | Tree health carryover |
| `year_numeric` | Calendar year | Long-term trend |

**Output:** `data/df_model.csv` (35 rows × 16 columns)

### 3. Model Training (`src/train_models.py`)

#### ARIMA Baseline (1990–2024)
- **Model**: ARIMA(1, 1, 1) on historical yield alone
- **Test Set**: 2023–2024
- **Metrics**:
  - RMSE: **2,105 lbs/acre**
  - MAE: **1,684 lbs/acre**
- **2024 Forecast**: 31,224 lbs/acre

#### LightGBM with Walk-Forward CV
- **Features**: Weather + lag + trend (12 engineered features)
- **Hyperparameters**:
  - learning_rate: 0.05
  - max_depth: 5
  - num_boost_round: 200
- **CV Strategy**: Expanding train window, test on 2023–2024
- **Metrics**: RMSE, MAE, SHAP feature importance
- **Top Features**: Frost days, temp variance, GDD, precipitation patterns

**Output:** `results/model_results.json`

### 4. Stress Indicator (`src/stress_indicator.py`)

Composite climate stress score:
```
stress_score = (
    0.4 × frost_stress +
    0.3 × precip_stress +
    0.2 × gdd_stress +
    0.1 × yield_health
)
```

Categories:
- **HIGH**: stress_score > 1.0 → Yield at risk
- **MODERATE**: 0.5 < score ≤ 1.0 → Caution advised
- **LOW**: score ≤ 0.5 → Favorable conditions

**Output:** `results/stress_indicator.csv`

### 5. Dashboard (`src/app.py`)

Interactive Plotly Dash application with 3 tabs:

#### Tab 1: Overview
- KPI cards: Current yield, 5-year trend, 2025 forecast, stress level
- Historical yield chart with ARIMA + LightGBM forecasts & confidence bands
- Stress index timeline

#### Tab 2: Weather Analysis
- 3 time-series subplots: Temperature, precipitation, frost days
- Feature importance bar chart (SHAP-like values from LightGBM)

#### Tab 3: Scenarios
- Interactive slider: Frost days increase (+0% to +50%)
- Yield impact bar chart (baseline vs scenario)
- Economic impact calculator:
  - Per-acre revenue loss @ $0.45/lb commodity price
  - County-wide impact (50,000 Polk County acres)

---

## Project Structure

```
Agriculture Project/
├── src/
│   ├── fetch_data.py           # USDA NASS + NOAA API integration
│   ├── feature_engineering.py  # Weather aggregation & feature calc
│   ├── train_models.py         # ARIMA + LightGBM modeling
│   ├── stress_indicator.py     # Climate stress scoring
│   └── app.py                  # Plotly Dash dashboard
├── data/
│   ├── nass_yield.csv          # Raw yield data (35 rows)
│   ├── noaa_weather.csv        # Raw weather data (5040 rows)
│   └── df_model.csv            # Final engineered features (35 rows × 16 cols)
├── results/
│   ├── model_results.json      # ARIMA & LightGBM metrics + forecasts
│   └── stress_indicator.csv    # Stress scores by year (35 rows)
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## Installation & Execution

### Prerequisites
- Python 3.9+
- pip package manager

### Setup
```bash
git clone <repo-url>
cd "Agriculture Project"
pip install -r requirements.txt
```

### Run Full Pipeline
```bash
# 1. Fetch data
python src/fetch_data.py

# 2. Engineer features
python src/feature_engineering.py

# 3. Train models
python src/train_models.py

# 4. Calculate stress indicator
python src/stress_indicator.py

# 5. Launch dashboard
python src/app.py
```

Dashboard runs at: **http://127.0.0.1:8050**

---

## Key Findings

### Model Performance
| Model | RMSE | MAE | Strength |
|-------|------|-----|----------|
| ARIMA(1,1,1) | 2,105 | 1,684 | Univariate baseline |
| LightGBM | *TBD* | *TBD* | Weather-aware |

### Feature Importance (LightGBM)
1. **Frost days during bloom** (Jan–Mar) — Highest impact on yield loss
2. **Temperature variance** (May–Aug) — Stability matters
3. **GDD accumulation** — Ripening progress
4. **Precipitation patterns** — Water stress
5. **Lag-1 yield** — Tree health carryover

### Agricultural Insights
- **Frost risk**: Primary driver of yield loss in Florida citrus
- **Precipitation**: Both excess (fungal disease) and deficit (stress) reduce yields
- **Long-term trend**: Declining yields (2002–2024) reflect Citrus Greening Disease (HLB) and grower exit
- **Stress clustering**: High-stress years (2020–2024) align with HLB endemic regions

---

## Deployment

### Hugging Face Spaces
Target deployment environment. Steps:

1. Create Hugging Face account (free tier)
2. Create "Spaces" repository with Git
3. Upload project files
4. Configure `requirements.txt` and `src/app.py` as the main entry point
5. Spaces auto-runs the Dash server

**URL**: `https://huggingface.co/spaces/[username]/florida-citrus-yield-forecast`

### Local Development
```bash
python src/app.py
# Navigate to http://localhost:8050
```

---

## Data Sources

### USDA NASS QuickStats API
- **Endpoint**: https://quickstats.nass.usda.gov/api/get
- **Query**: Citrus yield, Polk County, FL, 1990–2024
- **Fields**: year, county, yield_lbs_acre, data_quality

### NOAA Climate Data Online (CDO) API v1
- **Endpoint**: https://www.ncei.noaa.gov/access/services/data/v1
- **Dataset**: global-summary-of-the-day
- **Data Types**: TMAX, TMIN, PRCP
- **Stations**: Lakeland Linder, Tampa International, Orlando Executive, Sebring

---

## Industry Context

### The Florida Citrus Crisis
- **Production**: 100-year low in 2024/2025 season
- **Drivers**:
  - Citrus Greening Disease (HLB) — major loss factor
  - Hurricane Ian (2022) & Milton (2024) — tree damage & defoliation
  - Freeze events (2021, 2022) — blossom kill & fruit loss
  - Urban encroachment — land conversion
  - Grower exodus — 69% reduction in growers (2002–2022)

### Economic Impact
- **Commodity price**: ~$0.45/lb (check current market)
- **Polk County**: ~50,000 acres of citrus
- **Yield loss scenario** (+50% frost days): ~$50M+ county-wide loss

### Portfolio Angle
This forecasting system demonstrates:
1. ML-driven agricultural risk modeling
2. Integration of public APIs (USDA, NOAA)
3. Time-series + ensemble modeling for supply chain forecasting
4. Interactive dashboards for stakeholder communication

---

## Future Enhancements

1. **Multi-county expansion**: All major FL citrus counties (Orange, Citrus, Lake, etc.)
2. **Real-time updates**: Scheduled daily/weekly refreshes from USDA NASS & NOAA APIs
3. **Satellite imagery**: Incorporate NDVI, precipitation radar from satellite data
4. **Explainability**: SHAP force plots, partial dependence for grower decisions
5. **Economic module**: Integrate commodity futures pricing for ROI forecasting
6. **Mobile app**: React Native for field-side access

---

## References

- USDA NASS QuickStats: https://quickstats.nass.usda.gov/
- NOAA CDO: https://www.ncei.noaa.gov/cdo-web/
- Citrus Research & Education Center (UF): https://crec.ifas.ufl.edu/
- National Citrus Statistics: USDA ERS

---

## License

MIT License — See LICENSE file (if applicable)

---

**Last Updated**: July 2026  
**Maintainer**: Agricultural Data Science Team  
**Contact**: brian.blitz28@gmail.com
