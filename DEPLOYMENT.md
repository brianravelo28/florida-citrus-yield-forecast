# Deployment Guide — Hugging Face Spaces

Deploy the Citrus Yield Forecasting dashboard to Hugging Face Spaces (free tier).

## Prerequisites

- Hugging Face account (free at https://huggingface.co)
- Git installed locally
- Project directory with all files

## Step 1: Create Hugging Face Spaces Repository

1. Go to https://huggingface.co/spaces
2. Click **Create new Space**
3. Fill in:
   - **Space name**: `florida-citrus-yield-forecast`
   - **Space type**: `Docker` (we'll provide Dockerfile)
   - **License**: MIT (or your choice)
   - **Private/Public**: Public
4. Click **Create space**

## Step 2: Clone Your Space Repository

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/florida-citrus-yield-forecast
cd florida-citrus-yield-forecast
```

## Step 3: Add Project Files

Copy all project files into the cloned repository:

```bash
# From your local Agriculture Project directory
cp -r src/ requirements.txt README.md run_dashboard.py <HF_SPACES_REPO>/

# Or if using Windows cmd:
# xcopy src <HF_SPACES_REPO>\src /I
# copy requirements.txt <HF_SPACES_REPO>\
# copy README.md <HF_SPACES_REPO>\
# copy run_dashboard.py <HF_SPACES_REPO>\
```

## Step 4: Create Dockerfile

Create `Dockerfile` in your HF Spaces repo:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY data/ data/ 2>/dev/null || echo "Data files will be generated"
COPY results/ results/ 2>/dev/null || echo "Results will be generated"
COPY run_dashboard.py .

# Expose Dash port
EXPOSE 7860

# Run the dashboard
CMD ["python", "run_dashboard.py"]
```

## Step 5: Create `.gitignore`

```
*.pyc
__pycache__/
*.egg-info/
.DS_Store
venv/
.env
*.log
```

## Step 6: Push to Hugging Face

```bash
cd <HF_SPACES_REPO>
git add .
git commit -m "Initial commit: Citrus yield forecasting dashboard"
git push
```

Hugging Face will automatically:
1. Detect the `Dockerfile`
2. Build the container
3. Start the application
4. Assign you a public URL

---

## Alternative: Streamlit Deployment

If you prefer Streamlit over Dash, use this simpler approach:

### Create `streamlit_app.py`

```python
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json

st.set_page_config(page_title="Citrus Yield Forecast", layout="wide")

st.title("Florida Citrus Yield Forecasting")
st.markdown("USDA NASS + NOAA Weather + ML Forecasting")

# Load data
df_model = pd.read_csv("data/df_model.csv")
stress_data = pd.read_csv("results/stress_indicator.csv")

with open("results/model_results.json") as f:
    model_results = json.load(f)

# Tabs
tab1, tab2, tab3 = st.tabs(["Overview", "Weather", "Scenarios"])

with tab1:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Current Yield (2024)", "31,645 lbs/acre", "-10.1%")
    with col2:
        st.metric("5-Year Avg", "31,071 lbs/acre", None)
    with col3:
        st.metric("2025 Forecast", "31,224 lbs/acre", None)
    with col4:
        st.metric("Stress Level", "LOW", None)

    # Yield chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_model['year'], y=df_model['yield_lbs_acre'],
        mode='lines+markers', name='Historical Yield'
    ))
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader("Growing Season Weather")
    col1, col2, col3 = st.columns(3)
    col1.metric("Avg Max Temp", f"{df_model['tmax_mean_grow'].mean():.1f}°F")
    col2.metric("Avg Min Temp", f"{df_model['tmin_mean_grow'].mean():.1f}°F")
    col3.metric("Total Precip", f"{df_model['precip_total_grow'].mean():.2f}mm")

with tab3:
    frost_increase = st.slider("Frost Days Increase", 0, 50, 0)
    if frost_increase:
        st.info(f"Scenario: +{frost_increase}% frost days")
        st.write(f"Estimated yield loss: ~{frost_increase * 400:,.0f} lbs/acre")

st.divider()
st.markdown("**Data sources**: USDA NASS QuickStats, NOAA CDO v1 API")
```

### Create `requirements.txt` (same as original)

### Deploy:
```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/florida-citrus-yield-forecast
cd florida-citrus-yield-forecast
cp -r src/ data/ results/ streamlit_app.py requirements.txt .
git add .
git commit -m "Deploy Streamlit version"
git push
```

HF Spaces auto-detects `streamlit_app.py` and deploys instantly!

---

## Verification

After deployment completes:

1. **Check deployment status**: Visit your Space URL
2. **View logs**: Click "Logs" tab in Space settings
3. **Test functionality**:
   - Tab 1: View historical yield chart
   - Tab 2: Explore weather components
   - Tab 3: Adjust frost slider

## URL Format

Your dashboard will be live at:
```
https://huggingface.co/spaces/YOUR_USERNAME/florida-citrus-yield-forecast
```

## Updating Your Dashboard

To push updates:

```bash
cd <HF_SPACES_REPO>
# Make code changes locally
git add .
git commit -m "Update dashboard"
git push
# HF automatically rebuilds & redeploys
```

---

## Free Tier Limitations

- **CPU**: 2 vCPU (can be slow for large datasets)
- **Memory**: 16 GB
- **Storage**: 20 GB
- **Uptime**: Runs 24/7 (CPU sleeps after 48h inactivity, wakes on request)
- **Cost**: Free

**To upgrade**: Add GPU/more resources (paid tier ~$10/month)

---

## Environment Variables (Optional)

Store sensitive data securely:

1. Go to Space **Settings → Variables and secrets**
2. Add:
   - `NASS_API_KEY`: Your USDA NASS key
   - `NOAA_API_TOKEN`: Your NOAA token

Then update `src/fetch_data.py`:
```python
import os
NASS_KEY = os.getenv('NASS_API_KEY')
NOAA_TOKEN = os.getenv('NOAA_API_TOKEN')
```

---

## Troubleshooting

### "Build failed"
- Check `Dockerfile` syntax
- Ensure `requirements.txt` has correct package names
- Check Space logs for specific errors

### "Module not found at runtime"
- Add missing packages to `requirements.txt`
- Redeploy via `git push`

### "Data files not found"
- Pre-generate data locally, commit to repo:
  ```bash
  python src/fetch_data.py
  python src/feature_engineering.py
  git add data/ results/
  git push
  ```

### Slow dashboard
- Your Space may be on shared CPU
- Upgrade to paid tier or optimize code
- Cache data with `@st.cache_data` (Streamlit)

---

## Next Steps

1. **Real data**: Get API credentials, update keys
2. **Scheduled updates**: Use GitHub Actions to auto-fetch latest data weekly
3. **Custom domain**: Bind a custom domain to your Space
4. **Alerts**: Add email/Slack notifications for high-stress years
5. **Mobile**: Create React Native or Flutter companion app

---

**Questions?** See README.md or visit Hugging Face Spaces docs:
https://huggingface.co/docs/hub/spaces

---

**Deployment Time**: ~5 minutes setup + 2-5 minutes build  
**Monthly Cost**: $0 (free tier) or $10+ (paid tier with GPU)
