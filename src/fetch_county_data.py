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

Like fetch_data.py, a failed API request stops the run and writes nothing.
"""

import sys
import time
from pathlib import Path

import pandas as pd

from fetch_data import FetchError, START_YEAR, END_YEAR, get_json, is_plausible, require_key

Path("data").mkdir(exist_ok=True)

CENSUS_YEARS = ["2002", "2007", "2012", "2017", "2022"]

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
                "key": require_key("NASS_KEY"),
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


def fetch_station_weather(station_name, station_id):
    """Fetch one station's daily TMAX/TMIN/PRCP, START_YEAR-END_YEAR, as a list of rows.

    A year with no observations is legitimate (stations start and stop);
    a failed request is not, and raises FetchError via get_json.
    """
    url = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": require_key("NOAA_TOKEN")}
    rows, rejected, returned = [], 0, 0

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

            results = data.get("results", [])
            for record in results:
                try:
                    datatype = record.get("datatype")
                    value = float(record.get("value"))
                except (ValueError, TypeError):
                    continue

                if not is_plausible(datatype, value):
                    rejected += 1
                    continue

                rows.append({
                    "station_id": station_id,
                    "station_name": station_name,
                    "date": record.get("date", "")[:10],
                    "datatype": datatype,
                    "value": value,
                    "data_source": "NOAA",
                })

            returned += len(results)
            total_count = data.get("metadata", {}).get("resultset", {}).get("count", 0)
            if offset + 1000 > total_count:
                break
            offset += 1000
            time.sleep(0.2)

        time.sleep(0.15)

    rejected_note = f", {rejected} rejected (implausible)" if rejected else ""
    print(f"    [OK] {station_name} ({station_id}): {returned - rejected} records{rejected_note}")
    return rows


def fetch_all_county_weather():
    """Fetch every county's stations (each distinct station once) and label rows by county."""
    cache = {}
    all_rows = []

    for county_label, stations in COUNTY_STATIONS.items():
        print(f"  {county_label}:")
        for station_name, station_id in stations.items():
            if station_id not in cache:
                cache[station_id] = fetch_station_weather(station_name, station_id)
            else:
                print(f"    [OK] {station_name} ({station_id}): reusing fetched data")
            all_rows.extend({"county_name": county_label, **row} for row in cache[station_id])

    df = pd.DataFrame(all_rows)

    # Every county must have weather in every year, as the statewide fetch requires.
    years = pd.to_datetime(df["date"]).dt.year
    for county_label in COUNTY_STATIONS:
        missing = sorted(set(range(START_YEAR, END_YEAR + 1)) - set(years[df["county_name"] == county_label]))
        if missing:
            raise FetchError(f"{county_label} weather has no data for years: {missing}")
    return df


def main():
    print("=" * 60)
    print("COUNTY-LEVEL REAL DATA: Polk, Hendry, DeSoto, Highlands")
    print("=" * 60)

    # Fetch everything first; write only if every fetch succeeded.
    try:
        df_acreage = fetch_bearing_acreage()
        print("\nFetching local weather per county...")
        df_weather = fetch_all_county_weather()
    except FetchError as e:
        print(f"\n[FAILED] {e}")
        print("Nothing was written; existing data files are unchanged.")
        sys.exit(1)

    df_acreage.to_csv("data/county_acreage.csv", index=False)
    print(f"\n[OK] Saved: data/county_acreage.csv ({len(df_acreage)} records)")
    df_weather.to_csv("data/county_weather.csv", index=False)
    print(f"[OK] Saved: data/county_weather.csv ({len(df_weather)} records)")

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
