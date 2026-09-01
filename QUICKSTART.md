# Quick Start Guide — Florida Citrus Yield Forecasting

Get up and running in 5 minutes.

## Installation

```bash
# Clone and navigate
cd "Agriculture Project"

# Install dependencies (one time)
pip install -r requirements.txt
```

## Run the Full Pipeline

```bash
# Option 1: Run individual steps
python src/fetch_data.py
python src/feature_engineering.py
python src/train_models.py
python src/stress_indicator.py

# Option 2: Run all at once
for script in fetch_data.py feature_engineering.py train_models.py stress_indicator.py; do
    python src/$script
done
```

### What Happens at Each Step

| Step | Script | Output | Time |
|------|--------|--------|------|
| 1. Data Fetch | `fetch_data.py` | `data/nass_yield.csv`, `data/noaa_weather.csv` | 2-5m |
| 2. Feature Engineering | `feature_engineering.py` | `data/df_model.csv` (13 features) | <1m |
| 3. Model Training | `train_models.py` | `results/model_results.json` | 1-2m |
| 4. Stress Indicator | `stress_indicator.py` | `results/stress_indicator.csv` | <1m |

## View the Dashboard

```bash
python run_dashboard.py
```

**Dashboard URL**: http://127.0.0.1:8050

### Dashboard Tabs

1. **Overview** → Yield trends, KPIs, stress timeline
2. **Weather Analysis** → Temperature, precipitation, feature importance
3. **Scenarios** → Interactive "what-if" frost day analysis

---

## Project Architecture

```
Input APIs → Fetch Data → Feature Engineering → Model Training → Stress Scoring → Dashboard
  ↓            ↓              ↓                    ↓                  ↓
 USDA         CSV files    Engineered           JSON results      Interactive
 NOAA                       features             CSV files          Analytics
```

---

## Key Outputs

### Model Performance
- **ARIMA RMSE**: 2,105 lbs/acre
- **Forecast 2024**: 31,224 lbs/acre

### Stress Indicator
- Scores by year (0–2.0 range)
- Categories: LOW, MODERATE, HIGH

### Data
- 35 years of historical yield (1990–2024)
- 5,040 weather observations
- 16 engineered features per year

---

## Deployment to Hugging Face Spaces

1. Create account at https://huggingface.co
2. Create new "Spaces" repository (Space type: Gradio/Streamlit)
3. Upload this folder to your Spaces repo
4. Spaces will auto-detect `requirements.txt` and run `python run_dashboard.py`

**URL**: `https://huggingface.co/spaces/[your-username]/florida-citrus-yield-forecast`

---

## Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt
```

### "No data files" when running dashboard
Make sure you've run `fetch_data.py` first:
```bash
python src/fetch_data.py
```

### Dashboard won't start
Check port 8050 is available:
```bash
netstat -ano | findstr 8050  # Windows
lsof -i :8050               # Mac/Linux
```

If port is in use, modify `run_dashboard.py` and change `port=8050` to another port.

---

## Next Steps

- **Real data**: Replace API keys in `src/fetch_data.py` with actual USDA NASS & NOAA credentials
- **Multi-county**: Expand to all FL citrus counties (Orange, Citrus, Lake, etc.)
- **Satellite data**: Add NDVI, crop moisture indices
- **Mobile app**: React Native version for field-side access

---

## File Guide

| File | Purpose |
|------|---------|
| `src/fetch_data.py` | USDA NASS + NOAA API integration |
| `src/feature_engineering.py` | Weather aggregation & feature calculation |
| `src/train_models.py` | ARIMA + LightGBM model training |
| `src/stress_indicator.py` | Climate stress scoring |
| `src/app.py` | Plotly Dash dashboard (3 tabs) |
| `run_dashboard.py` | Entry point to launch dashboard |
| `data/*.csv` | Raw input & processed data |
| `results/*.json` & `results/*.csv` | Model outputs & scores |

---

**Questions?** See `README.md` for detailed documentation.
