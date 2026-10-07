"""
Fetch real, county-specific data for four large Florida orange-producing
counties: Polk, Hendry, DeSoto, Highlands.

Unlike fetch_data.py (which sources statewide YIELD, since NASS publishes no
county-level citrus PRODUCTION/YIELD in any year or source we checked,
including the Census of Agriculture), this script pulls only what NASS
actually publishes at the county level - bearing ACREAGE, in Census years
(every 5 years; some totals are withheld by USDA and left blank, never
estimated) - plus real local daily weather from verified NOAA
stations physically in or near each county.

No yield/production numbers are fabricated here. This produces two
real, independently-sourced datasets per county:
  - acreage history (real Census figures, 2002/2007/2012/2017/2022)
  - local daily weather (real NOAA station observations, 1990-2024)
"""

import requests
import pandas as pd
import time
from pathlib import Path

from fetch_data import FetchError, get_json

NASS_KEY = "C239BF21-79EB-3B84-B273-9CE323601358"
NOAA_TOKEN = "ytMyljSmGhKmcJeNITGlrpqFZBHopvJP"

Path("data").mkdir(exist_ok=True)

CENSUS_YEARS = ["2002", "2007", "2012", "2017", "2022"]

# Physically-motivated sanity bounds for central/south FL daily readings
# (units=standard: TMAX/TMIN in deg F, PRCP in inches). Florida's all-time
# record high is 109F (1931); record low in this region is well above the
# panhandle's -2F. Bounds are deliberately generous so real extreme-weather
# days (freezes, hurricanes) pass through - this only catches the kind of
# single-point sensor/transcription errors found in the co-op station data
# (e.g. a 0F or 115F daily high, both physically implausible for FL).
TMAX_BOUNDS = (20.0, 110.0)
TMIN_BOUNDS = (-5.0, 85.0)
PRCP_BOUNDS = (0.0, 20.0)


def is_plausible(datatype, value):
    """Reject physically implausible readings (sensor/transcription errors)."""
    if datatype == "TMAX":
        return TMAX_BOUNDS[0] <= value <= TMAX_BOUNDS[1]
    if datatype == "TMIN":
        return TMIN_BOUNDS[0] <= value <= TMIN_BOUNDS[1]
    if datatype == "PRCP":
        return PRCP_BOUNDS[0] <= value <= PRCP_BOUNDS[1]
    return True

# NASS county_name spelling quirks (DeSoto is "DE SOTO" in QuickStats)
NASS_COUNTIES = {
    "Polk": "POLK",
    "Hendry": "HENDRY",
    "DeSoto": "DE SOTO",
    "Highlands": "HIGHLANDS",
}

# Verified-working NOAA GHCND stations per county (tested directly against
# the /data endpoint across multiple decades - station catalog metadata
# alone is not reliable, e.g. Bartow is a registered station that returns
# zero observations in every year tested). Clewiston (USC00081654) is a
# usable Hendry County station for 1990-2003 that is not currently included.
COUNTY_STATIONS = {
    "Polk": {
        "Lakeland Linder": "USW00012883",
        "Tampa International": "USW00012842",
        "Orlando Executive": "USW00012841",
        "Sebring": "USW00092827",
    },
    "Hendry": {
        "La Belle": "USC00084662",
        "Moore Haven Lock 1": "USC00085895",
    },
    "DeSoto": {
        "Arcadia": "USC00080228",
        "Punta Gorda Airport": "USW00012812",
    },
    "Highlands": {
        "Avon Park 2 W": "USC00080369",
        "Sebring": "USW00092827",
    },
}


def fetch_bearing_acreage():
    """Fetch ORANGES bearing acreage (all varieties combined) per county, Census years only.

    Returns one row per county and Census year, with a status:
      published - USDA published the all-varieties total.
      withheld  - USDA withheld it ("(D)": withheld to avoid disclosing
                  individual operations' data). bearing_acres is left blank
                  and is never estimated.

    A county-year can return several rows (ALL CLASSES plus single varieties
    such as VALENCIA). Only the ALL CLASSES total is a county total: when it is
    withheld, a published single variety must not be used in its place.
    """
    print("Fetching bearing acreage (Census years, real NASS data)...")
    records = []

    for county_label, nass_name in NASS_COUNTIES.items():
        for year in CENSUS_YEARS:
            params = {
                "key": NASS_KEY,
                "commodity_desc": "ORANGES",
                "state_alpha": "FL",
                "county_name": nass_name,
                "source_desc": "CENSUS",
                "year": year,
                "statisticcat_desc": "AREA BEARING",
                "unit_desc": "ACRES",
                "class_desc": "ALL CLASSES",
                "domain_desc": "TOTAL",
                "format": "json",
            }
            rows = get_json("https://quickstats.nass.usda.gov/api/api_GET/", params).get("data", [])
            if len(rows) != 1:
                raise FetchError(
                    f"expected exactly one ALL CLASSES total for {county_label} {year}, got {len(rows)}"
                )

            raw = str(rows[0].get("Value", "")).strip()
            if raw == "(D)":
                acres, status = float("nan"), "withheld"
            else:
                try:
                    acres, status = float(raw.replace(",", "")), "published"
                except ValueError:
                    raise FetchError(f"unexpected acreage value {raw!r} for {county_label} {year}")

            records.append({
                "county_name": county_label,
                "year": int(year),
                "bearing_acres": acres,
                "status": status,
                "data_source": "NASS_CENSUS",
            })
            time.sleep(0.1)

        mine = [r for r in records if r["county_name"] == county_label]
        n_pub = sum(r["status"] == "published" for r in mine)
        print(f"  [OK] {county_label}: {n_pub} published, {len(mine) - n_pub} withheld")

    return pd.DataFrame(records)


def fetch_county_weather(county_label, stations):
    """Fetch real daily NOAA weather for one county's verified stations."""
    url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": NOAA_TOKEN}
    all_weather = []

    for station_name, station_id in stations.items():
        print(f"    Fetching {station_name} ({station_id})...")
        station_count = 0

        station_rejected = 0

        for year in range(1990, 2025):
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
                try:
                    resp = requests.get(url, headers=headers, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    print(f"      [!] {station_name} {year}: {e}")
                    break

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
                        "county_name": county_label,
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
                time.sleep(0.2)

            time.sleep(0.15)

        rejected_note = f", {station_rejected} rejected (implausible)" if station_rejected else ""
        print(f"      [OK] {station_name}: {station_count - station_rejected} records{rejected_note}")

    return all_weather


def main():
    print("=" * 60)
    print("COUNTY-LEVEL REAL DATA: Polk, Hendry, DeSoto, Highlands")
    print("=" * 60)

    # 1. Bearing acreage (real, Census years)
    df_acreage = fetch_bearing_acreage()
    df_acreage.to_csv("data/county_acreage.csv", index=False)
    print(f"\n[OK] Saved: data/county_acreage.csv ({len(df_acreage)} records)")

    # 2. Local weather (real, daily, 1990-2024)
    print("\nFetching local weather per county...")
    all_records = []
    for county_label, stations in COUNTY_STATIONS.items():
        print(f"  {county_label}:")
        all_records.extend(fetch_county_weather(county_label, stations))

    df_weather = pd.DataFrame(all_records)
    df_weather.to_csv("data/county_weather.csv", index=False)
    print(f"\n[OK] Saved: data/county_weather.csv ({len(df_weather)} records)")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("\nBearing acreage by county (2022, most recent):")
    latest = df_acreage[df_acreage["year"] == 2022].sort_values("bearing_acres", ascending=False)
    print(latest.to_string(index=False))

    print("\nWeather records by county:")
    print(df_weather.groupby("county_name").size().sort_values(ascending=False).to_string())


if __name__ == "__main__":
    main()
