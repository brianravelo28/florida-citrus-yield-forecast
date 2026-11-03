# Render Deployment

Live: <https://florida-orange-yield-dashboard.onrender.com/>

On the free tier the service sleeps when idle, so the first request after a pause can take about 40 seconds.

## Service settings

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn src.app:server --bind 0.0.0.0:$PORT` |
| Auto-deploy | On push to `main` |

`src/app.py` exposes the Flask server as `server` for gunicorn. `render.yaml` in the repo root records these settings as a reference.

**Python version.** The service sets `PYTHON_VERSION` to `3.14.8` in its Environment settings in the Render dashboard (set 2026-10-28). Render requires the full `x.y.z` form for this variable. `requirements.txt` is pinned to package versions tested on Python 3.14, and CI tests Python 3.13 and 3.14. `render.yaml` lists the same value as a reference, but the live service is configured in the dashboard, not from that file.

## Data files must be committed

The app reads `data/*.csv` at import time, so the files below must be committed. If a deploy crashes with `FileNotFoundError: data/...csv`, a required file is missing from the repo.

The files the app loads: `data/nass_yield.csv`, `data/county_features.csv`, `data/stations.csv`, `data/station_frost_summary.csv`.

## Updating

Regenerate the data locally (see the README pipeline), commit the changed files, and push; Render redeploys automatically. API keys are not needed at runtime, because the dashboard only reads the committed files.
