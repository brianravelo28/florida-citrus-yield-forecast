"""
Fetch Florida statewide orange yield from USDA NASS QuickStats, 1990-2026,
and hold the helpers shared by the other fetch scripts (API client, plausibility
bounds, key lookup).

If an API call fails, the run stops with an error and writes nothing. There is
deliberately no fallback to substitute data: a failed fetch must never produce
files that look like real data.
"""

import os
import sys
import time
from pathlib import Path

import pandas as pd
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

FL_ORANGE_BOX_LBS = 90  # Standard FDOC/USDA Florida orange box weight (lbs)


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


def fetch_nass_yield():
    """Fetch FL statewide orange yield from USDA NASS (START_YEAR-END_YEAR).

    QuickStats has no county-level orange yield or production: county rows
    for oranges and citrus totals cover Census area statistics only. (NASS's
    Citrus Summary publication does list county production, but those are
    apportionments of the statewide harvest, not county measurements.) Yield
    is only available at STATE level, reported in BOXES/ACRE, which we convert
    to LB/ACRE using the standard FL orange box weight (90 lbs/box).
    """
    print("Fetching USDA NASS Florida orange yield data...")

    params = {
        "key": require_key("NASS_KEY"),
        "commodity_desc": "ORANGES",
        "state_alpha": "FL",
        "agg_level_desc": "STATE",
        "statisticcat_desc": "YIELD",
        "unit_desc": "BOXES / ACRE",
        "class_desc": "ALL CLASSES",
        "util_practice_desc": "ALL UTILIZATION PRACTICES",
        "year__GE": str(START_YEAR),
        "year__LE": str(END_YEAR),
        "format": "json",
    }
    data = get_json("https://quickstats.nass.usda.gov/api/api_GET/", params)

    rows = data.get("data")
    if not rows:
        raise FetchError(f"NASS returned no yield records ({data.get('error', 'no error message')})")

    records = []
    for row in rows:
        val = str(row.get("Value", "")).strip()
        # Skip suppressed/unavailable values
        if val in ("", "(D)", "(NA)", "(S)", "(Z)"):
            continue
        try:
            year = int(row.get("year"))
            records.append({
                "county_name": "Florida (Statewide)",
                "year": year,
                "yield_lbs_acre": float(val.replace(",", "")) * FL_ORANGE_BOX_LBS,
                "status": "preliminary" if year in PRELIMINARY_YEARS else "reported",
                "data_source": "NASS",
            })
        except (ValueError, TypeError):
            continue

    df = pd.DataFrame(records)
    df = df[(df["year"] >= START_YEAR) & (df["year"] <= END_YEAR)]
    df = df.sort_values("year").reset_index(drop=True)

    missing = sorted(set(range(START_YEAR, END_YEAR + 1)) - set(df["year"]))
    if missing:
        raise FetchError(f"NASS yield is missing years: {missing}")
    if df["year"].duplicated().any():
        raise FetchError("NASS returned more than one yield row for a year")

    print(f"  [OK] Fetched {len(df)} yield records ({START_YEAR}-{END_YEAR}; {END_YEAR} is preliminary)")
    return df


def main():
    print("=" * 60)
    print("CITRUS DATA - STATEWIDE ORANGE YIELD")
    print("=" * 60)

    # Fetch first; write only if the fetch succeeded.
    try:
        df_yield = fetch_nass_yield()
    except FetchError as e:
        print(f"\n[FAILED] {e}")
        print("Nothing was written; existing data files are unchanged.")
        sys.exit(1)

    df_yield.to_csv("data/nass_yield.csv", index=False)
    print(f"\n[OK] Saved: data/nass_yield.csv")

    print("\nRecent years (lb/acre):")
    print(df_yield.tail(6)[["year", "yield_lbs_acre", "status"]].to_string(index=False))
    peak = df_yield.loc[df_yield["yield_lbs_acre"].idxmax()]
    low = df_yield.loc[df_yield["yield_lbs_acre"].idxmin()]
    print(f"\nPeak {int(peak['year'])}: {peak['yield_lbs_acre']:,.0f}   Low {int(low['year'])}: {low['yield_lbs_acre']:,.0f}   "
          f"(low is {1 - low['yield_lbs_acre'] / peak['yield_lbs_acre']:.0%} below the peak)")


if __name__ == "__main__":
    main()
