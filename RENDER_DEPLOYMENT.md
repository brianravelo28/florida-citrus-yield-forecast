# Render Deployment

Live: <https://us-citrus-industry-dashboard.onrender.com/>

On the free tier the service sleeps when idle, so the first request after a pause can take about 40 seconds.

## Service settings

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn src.app:server --bind 0.0.0.0:$PORT` |
| Health check path | `/healthz` |
| Auto-deploy | On push to `main` |

`src/app.py` exposes the Flask server as `server` for gunicorn. `render.yaml` in the repo root records these settings as a reference.

**Python version.** The service sets `PYTHON_VERSION` to `3.14.8` in its Environment settings in the Render dashboard (set 2026-10-28). Render requires the full `x.y.z` form for this variable. `requirements.txt` is pinned to package versions tested on Python 3.14, and CI tests Python 3.13 and 3.14. `render.yaml` lists the same value as a reference, but the live service is configured in the dashboard, not from that file.

## Endpoints for the host

- `/healthz` returns `{"status": "ok"}` with status 200 once the app has loaded its data. It is a real endpoint, not the Dash front page, so it can serve as the service's health check; set it under Settings, Health Check Path in the Render dashboard (the dashboard's settings override `render.yaml`).
- `/debugz` returns what is running: start time and uptime, process id, Python and package versions, the row counts of the loaded data files, and the process's memory in MB. On Linux (Render) the memory is the current resident set; where that is not available it is the peak, or `null`. Read the hosted figure from the live service after a deploy, not from a local run. It reports no keys or environment variables.

## Data files must be committed

The app reads `data/*.csv` at import time, so the files below must be committed. If a deploy crashes with `FileNotFoundError: data/...csv`, a required file is missing from the repo.

The files the app loads: `data/citrus_by_state.csv`, `data/citrus_totals_by_state.csv` and `data/cpi_u_monthly.csv`.

## Updating

Regenerate the data locally (see the README pipeline), commit the changed files, and push; Render redeploys automatically. API keys are not needed at runtime, because the dashboard only reads the committed files.
