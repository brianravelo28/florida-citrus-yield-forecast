"""
Fetch Florida orange yield (USDA NASS) and central-Florida daily weather
(NOAA GHCND) for 1990-2024.

If any API call fails, the run stops with an error and writes nothing.
There is deliberately no fallback to substitute data: a failed fetch must
never produce files that look like real data.
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

# API credentials - replace with your own free keys (see README).
NASS_KEY = "C239BF21-79EB-3B84-B273-9CE323601358"
NOAA_TOKEN = "ytMyljSmGhKmcJeNITGlrpqFZBHopvJP"

START_YEAR, END_YEAR = 1990, 2024

# Ensure data directory exists
Path("data").mkdir(exist_ok=True)

# Physically-motivated sanity bounds for central FL daily readings
# (units=standard: TMAX/TMIN in deg F, PRCP in inches). See
# src/fetch_county_data.py for full rationale - kept in sync here so any
# re-fetch of state-level weather gets the same protection.
TMAX_BOUNDS = (20.0, 110.0)
TMIN_BOUNDS = (-5.0, 85.0)
PRCP_BOUNDS = (0.0, 20.0)

FL_ORANGE_BOX_LBS = 90  # Standard FDOC/USDA Florida orange box weight (lbs)


class FetchError(RuntimeError):
    """A data fetch failed. Nothing should be written when this is raised."""


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
    """Fetch FL statewide orange yield from USDA NASS (1990-2024).

    County-level citrus YIELD/PRODUCTION is not published by NASS (county
    level only has AREA statistics). Yield is only available at STATE
    level, reported in BOXES/ACRE, which we convert to LB/ACRE using the
    standard FL orange box weight (90 lbs/box).
    """
    print("Fetching USDA NASS Florida orange yield data...")

    params = {
        "key": NASS_KEY,
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
            records.append({
                "county_name": "Florida (Statewide)",
                "year": int(row.get("year")),
                "yield_lbs_acre": float(val.replace(",", "")) * FL_ORANGE_BOX_LBS,
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

    print(f"  [OK] Fetched {len(df)} yield records")
    return df


def fetch_noaa_weather():
    """Fetch daily TMAX/TMIN/PRCP from NOAA CDO v2 for central Florida stations."""
    print("Fetching NOAA weather data...")

    # GHCND airport station IDs, verified to return TMAX/TMIN/PRCP.
    # Lakeland Linder is physically inside Polk County; Tampa and Orlando
    # are the nearest major hubs (all three cover 1990-2024 continuously).
    # Sebring only has data from 2007-12-09 onward, but is included anyway
    # since it strengthens the multi-station average for 2008+ years
    # without affecting earlier years (pivot averaging just skips it).
    # (Bartow, also in Polk County, only reports PRCP - no temperature
    # data - so it's excluded entirely.)
    stations = {
        "Lakeland Linder": "USW00012883",
        "Tampa International": "USW00012842",
        "Orlando Executive": "USW00012841",
        "Sebring": "USW00092827",
    }

    url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": NOAA_TOKEN}

    all_weather = []

    for station_name, station_id in stations.items():
        print(f"  Fetching {station_name} ({station_id})...")
        station_count = 0
        station_rejected = 0

        # CDO v2 requires <1 year per request, so loop year by year
        for year in range(START_YEAR, END_YEAR + 1):
            offset = 1
            while True:
                params = {
                    "datasetid": "GHCND",
                    "stationid": f"GHCND:{station_id}",
                    "startdate": f"{year}-01-01",
                    "enddate": f"{year}-12-31",
                    "datatypeid": "TMAX,TMIN,PRCP",
                    "units": "standard",
                    "limit": 1000,
                    "offset": offset,
                }
                data = get_json(url, params, headers=headers)

                # An empty result is legitimate (e.g. Sebring before 2007);
                # a failed request is not, and raised above.
                results = data.get("results", [])
                for record in results:
                    try:
                        datatype = record.get("datatype")
                        value = float(record.get("value"))
                    except (ValueError, TypeError):
                        continue

                    if not is_plausible(datatype, value):
                        station_rejected += 1
                        continue

                    all_weather.append({
                        "station_id": station_id,
                        "station_name": station_name,
                        "date": record.get("date", "")[:10],
                        "datatype": datatype,
                        "value": value,
                        "data_source": "NOAA",
                    })

                station_count += len(results)
                total_count = data.get("metadata", {}).get("resultset", {}).get("count", 0)

                if offset + 1000 > total_count:
                    break
                offset += 1000
                time.sleep(0.2)  # respect rate limit (5 req/sec)

            time.sleep(0.2)

        rejected_note = f", {station_rejected} rejected (implausible)" if station_rejected else ""
        print(f"    [OK] {station_name}: {station_count - station_rejected} records{rejected_note}")

    if not all_weather:
        raise FetchError("NOAA returned no weather records")

    df = pd.DataFrame(all_weather)

    years_present = set(pd.to_datetime(df["date"]).dt.year)
    missing = sorted(set(range(START_YEAR, END_YEAR + 1)) - years_present)
    if missing:
        raise FetchError(f"NOAA weather has no data for years: {missing}")

    print(f"  [OK] Total weather records: {len(df)}")
    return df


def main():
    print("=" * 60)
    print("CITRUS YIELD FORECASTING - DATA FETCHING")
    print("=" * 60)

    # Fetch everything first; write only if every fetch succeeded.
    try:
        df_yield = fetch_nass_yield()
        df_weather = fetch_noaa_weather()
    except FetchError as e:
        print(f"\n[FAILED] {e}")
        print("Nothing was written; existing data files are unchanged.")
        sys.exit(1)

    df_yield.to_csv("data/nass_yield.csv", index=False)
    print(f"\n[OK] Saved: data/nass_yield.csv")
    df_weather.to_csv("data/noaa_weather.csv", index=False)
    print(f"[OK] Saved: data/noaa_weather.csv")

    # Print schemas
    print("\n" + "=" * 60)
    print("DATA SCHEMAS")
    print("=" * 60)

    print("\nYIELD DATA (NASS):")
    print(f"  Shape: {df_yield.shape}")
    print(f"  Columns: {list(df_yield.columns)}")
    print(f"  Year range: {df_yield['year'].min()} - {df_yield['year'].max()}")
    print(f"  Yield range: {df_yield['yield_lbs_acre'].min():.0f} - {df_yield['yield_lbs_acre'].max():.0f} lbs/acre")
    print(f"\n  First 5 rows:")
    print(df_yield.head().to_string(index=False))

    print("\n\nWEATHER DATA (NOAA):")
    print(f"  Shape: {df_weather.shape}")
    print(f"  Columns: {list(df_weather.columns)}")
    print(f"  Date range: {df_weather['date'].min()} - {df_weather['date'].max()}")
    print(f"  Data types: {df_weather['datatype'].unique().tolist()}")
    print(f"  Stations: {df_weather['station_name'].nunique()} unique")
    print(f"\n  First 5 rows:")
    print(df_weather.head().to_string(index=False))

    print("\n" + "=" * 60)
    print("Next: Run src/feature_engineering.py to merge & engineer features")
    print("=" * 60)


if __name__ == "__main__":
    main()
