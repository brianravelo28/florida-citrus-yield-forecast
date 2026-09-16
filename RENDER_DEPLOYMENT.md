# Render Deployment Guide

Deploy the Citrus Yield Forecasting dashboard to **Render** (free tier available).

## Overview

**Render** is a modern cloud platform perfect for hosting Dash applications:
- ✅ Free tier available
- ✅ Auto-deploys from GitHub
- ✅ Zero configuration needed
- ✅ Built-in SSL/HTTPS
- ✅ Environment variables & secrets
- ✅ 24/7 uptime (no sleep mode)

**Cost**: Free tier (limited resources) or ~$7/month (production)

---

## Prerequisites

1. ✅ **GitHub repository** (already done: `brianravelo28/florida-citrus-yield-forecast`)
2. ✅ **Render account** (free at https://render.com)
3. ✅ **render.yaml** (already created in repo root)

---

## Step 1: Connect GitHub to Render

1. Go to https://render.com and sign up (free account)
2. Click **"New +"** → **"Web Service"**
3. Click **"Connect a repository"**
4. Authorize Render to access your GitHub
5. Search for `florida-citrus-yield-forecast`
6. Click **"Connect"**

---

## Step 2: Configure Deployment

After connecting the repo, Render will auto-detect `render.yaml`:

| Setting | Value |
|---------|-------|
| **Name** | `citrus-yield-forecast` (auto-filled) |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` (auto) |
| **Start Command** | `gunicorn src.app:server --bind 0.0.0.0:$PORT` (auto) |
| **Plan** | Free (or Paid for better performance) |

✅ **All auto-configured!** Just click **"Create Web Service"**

---

## Step 3: Wait for Deployment

Render will:
1. Clone your repo
2. Install dependencies (`pip install -r requirements.txt`)
3. Build the Docker image
4. Deploy to a public URL

**Deployment time**: ~2-3 minutes

**Build logs**: Watch the live logs in the dashboard

---

## Step 4: Access Your Dashboard

Once deployed, Render provides a public URL like:

```
https://citrus-yield-forecast.onrender.com
```

✅ **Your dashboard is live!**

---

## Environment Variables (Optional)

To add API credentials for real data:

1. Go to your Render service dashboard
2. Click **"Environment"**
3. Add variables:
   ```
   NASS_API_KEY = your_nass_key
   NOAA_API_TOKEN = your_noaa_token
   ```

4. Update `src/fetch_data.py` to read from env:
   ```python
   import os
   NASS_KEY = os.getenv("NASS_API_KEY", "fallback_key")
   NOAA_TOKEN = os.getenv("NOAA_API_TOKEN", "fallback_token")
   ```

5. Re-deploy: Push to GitHub (auto-redeploy) or click **"Deploy"** in dashboard

---

## Auto-Deploy from GitHub

✅ **Enabled by default!**

Every time you push to `main`:
1. Render detects the push
2. Rebuilds and redeploys automatically
3. Zero downtime (rolling deployment)

**To disable**: Go to Service Settings → Auto-Deploy → Off

---

## File Structure for Render

```
florida-citrus-yield-forecast/
├── render.yaml              ← Render config (auto-detected)
├── requirements.txt         ← Python dependencies
├── src/
│   ├── app.py              ← Dash app (must have: server = app.server)
│   ├── fetch_data.py
│   ├── feature_engineering.py
│   ├── train_models.py
│   └── stress_indicator.py
├── data/                   ← Will be created on first run
└── results/                ← Will be created on first run
```

---

## Troubleshooting

### "Build failed"
- Check build logs in Render dashboard
- Ensure `requirements.txt` has all dependencies
- Verify `render.yaml` syntax (YAML indentation matters)

### "Port binding error"
- Render auto-sets `$PORT` environment variable
- `render.yaml` already handles this: `--bind 0.0.0.0:$PORT`
- No changes needed

### "Data files not found"
- First deployment may not have data files
- They're created when pipeline runs
- Two solutions:
  1. Run pipeline locally, commit CSV files to `/data` and `/results` (not recommended)
  2. Create a setup script that auto-runs on deployment

### "App takes too long to load"
- Free tier has limited CPU/memory
- Upgrade to paid tier for faster performance
- Or reduce data size (cache only recent years)

### "Need to restart without redeploying"
- Go to Render dashboard
- Click **"Manual Deploy"** → **"Deploy latest commit"**
- Or click **"Restart"** (no rebuild)

---

## Monitoring & Logs

### View Logs
1. Go to your service on Render
2. Click **"Logs"**
3. See real-time application output

### Monitor Performance
1. Click **"Metrics"**
2. View:
   - CPU usage
   - Memory usage
   - Request count
   - Response time

---

## Custom Domain (Optional)

1. Go to your service → **"Settings"**
2. Scroll to **"Custom Domain"**
3. Add your domain (e.g., `citrus-forecast.com`)
4. Follow DNS setup instructions
5. Render manages SSL certificates automatically ✅

---

## Updating Code

### Auto-Deploy from GitHub (Recommended)
```bash
git push origin main
# Render automatically redeploys
```

### Manual Updates
1. Make changes locally
2. Commit and push: `git push origin main`
3. Render detects and auto-deploys (~2-3 min)

### Force Redeploy
1. Go to Render service dashboard
2. Click **"Manual Deploy"** → **"Deploy latest commit"**

---

## Performance Tips

### Free Tier Limits
- **CPU**: Shared, variable
- **Memory**: 512 MB
- **Sleep**: ✅ Always on (no sleep mode like HF Spaces)
- **Bandwidth**: 100 GB/month

### Upgrade to Paid ($7/month)
- **CPU**: Dedicated
- **Memory**: 1 GB
- **SSD Storage**: 10 GB
- Better performance for data processing

### Optimize App
1. **Cache data**: Load CSVs once at startup
2. **Lazy imports**: Import heavy libraries only when needed
3. **Reduce data size**: Keep only recent years (e.g., 2010-2024)

---

## Comparison: Render vs. Hugging Face Spaces

| Feature | Render (Free) | Render (Paid) | HF Spaces |
|---------|---------------|---------------|-----------|
| **Cost** | Free | $7/month | Free |
| **Uptime** | 24/7 | 24/7 | 24/7 (no sleep) |
| **Auto-deploy** | ✅ Yes | ✅ Yes | Manual |
| **Memory** | 512 MB | 1 GB | 16 GB |
| **Setup** | Auto (render.yaml) | Auto | Manual |
| **Custom domain** | ✅ Yes | ✅ Yes | ❌ No |
| **Performance** | Shared | Dedicated | Good |

**Recommendation**: Start with **Render Free** tier, upgrade to **Paid** if needed

---

## Next Steps

1. ✅ **Push to GitHub**: Done (`brianravelo28/florida-citrus-yield-forecast`)
2. ✅ **Add render.yaml**: Done
3. ✅ **Connect Render**: Go to https://render.com
4. 🚀 **Deploy**: Authorize GitHub + click "Create Web Service"
5. 📊 **Share**: Get your live dashboard URL

---

## Dashboard URL (After Deployment)

Once live, your dashboard will be at:

```
https://citrus-yield-forecast.onrender.com
```

Share this URL with stakeholders, add to GitHub README, or customize with a domain!

---

## Support

- **Render Docs**: https://render.com/docs
- **Dash Deployment**: https://dash.plotly.com/deployment
- **Gunicorn Docs**: https://docs.gunicorn.org/

---

**You're ready to deploy!** 🚀
