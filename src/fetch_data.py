"""
Helpers shared by the fetch scripts: the API client with retries, key lookup,
the plausibility bounds for weather readings, and the year range and the
preliminary-season rule. Run the fetch scripts themselves (fetch_industry_data.py,
fetch_county_data.py, ...), not this file.

If an API call fails, a fetch script stops with an error and writes nothing.
There is deliberately no fallback to substitute data: a failed fetch must never
produce files that look like real data.
"""

import os
import time
from pathlib import Path

import requests


START_YEAR, END_YEAR = 1990, 2026

# NASS labels a Florida citrus season by its END year: 2023 is the 2022-23
# season. NASS publishes the season that ends in END_YEAR as a preliminary
# estimate in August and revises it a year later, so only that last year is
# marked "preliminary".
PRELIMINARY_YEARS = {END_YEAR}

# Ensure data directory exists
Path("data").mkdir(exist_ok=True)

# Physically-motivated sanity bounds for central/south FL daily readings
# (units=standard: TMAX/TMIN in deg F, PRCP in inches), used by the county
# weather fetch. Florida's all-time record high is 109F (1931). The bounds are
# deliberately generous so real extremes (freezes, hurricanes) pass through;
# they only catch single-point sensor or transcription errors seen in the
# co-op station data (e.g. a 0F or 115F daily high, or a 101F daily low).
TMAX_BOUNDS = (20.0, 110.0)
TMIN_BOUNDS = (-5.0, 85.0)
PRCP_BOUNDS = (0.0, 20.0)


class FetchError(RuntimeError):
    """A data fetch failed. Nothing should be written when this is raised."""


def require_key(name):
    """Read an API credential from the environment; fail clearly if it is unset.

    Keys are free (see README). They are read at fetch time, not import time,
    so importing helpers from this module never requires credentials, and
    the error never echoes a value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise FetchError(f"{name} is not set. Get a free key (see README) and export it as an environment variable.")
    return value


def noaa_token():
    """NOAA CDO token from NOAA_API_KEY (preferred) or NOAA_TOKEN."""
    for name in ("NOAA_API_KEY", "NOAA_TOKEN"):
        if os.environ.get(name, "").strip():
            return require_key(name)
    raise FetchError("NOAA_API_KEY is not set. Get a free token (see README) and export it as an environment variable.")


def is_plausible(datatype, value):
    """Reject physically implausible readings (sensor/transcription errors)."""
    if datatype == "TMAX":
        return TMAX_BOUNDS[0] <= value <= TMAX_BOUNDS[1]
    if datatype == "TMIN":
        return TMIN_BOUNDS[0] <= value <= TMIN_BOUNDS[1]
    if datatype == "PRCP":
        return PRCP_BOUNDS[0] <= value <= PRCP_BOUNDS[1]
    return True


def get_json(url, params, headers=None, attempts=3):
    """GET and parse JSON, retrying transient failures; raise FetchError if all fail.

    Error text deliberately omits the request URL: requests' own messages
    include it, and the NASS key travels in the query string.
    """
    reason = "unknown error"
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            reason = f"HTTP {e.response.status_code}"
        except (requests.RequestException, ValueError) as e:
            reason = type(e).__name__
        if attempt < attempts:
            time.sleep(2 ** attempt)
    raise FetchError(f"{url} failed after {attempts} attempts ({reason})")
