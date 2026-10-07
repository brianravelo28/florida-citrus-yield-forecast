# Render Deployment

Live: <https://florida-citrus-yield-forecast.onrender.com/>

On the free tier the service sleeps when idle, so the first request after a pause can take about 40 seconds.

## Service settings

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn src.app:server --bind 0.0.0.0:$PORT` |
| Auto-deploy | On push to `main` |

`src/app.py` exposes the Flask server as `server` for gunicorn. `render.yaml` in the repo root records these settings.

## Data files must be committed

The app reads `data/*.csv` and `results/*` at import time. `.gitignore` excludes `data/*.csv` and `results/*.json` by default, so the files the app needs were added with `git add -f`. If a deploy crashes with `FileNotFoundError: data/...csv`, a required file is missing from the repo.

The files the app loads: `data/df_model.csv`, `data/county_features.csv`, `results/stress_indicator.csv`, `results/model_results.json`.

## Updating

Regenerate the data locally (see the README pipeline), commit the changed files, and push; Render redeploys automatically. API keys are not needed at runtime, because the dashboard only reads the committed files.
