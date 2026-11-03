"""
Fetch bearing orange acreage for EVERY Florida county in each Census of
Agriculture year, so the choice of the four panel counties (Polk, Hendry,
DeSoto, Highlands) can be checked against the full county list.

Output: data/census_orange_acres_by_county.csv, one row per county and Census
year. A total USDA withheld ("(D)") is left blank with status "withheld" and
is never estimated. Needs NASS_KEY; a failed request stops the run and writes
nothing.
"""

import sys
import time

import pandas as pd

from fetch_county_data import CENSUS_YEARS, parse_acreage_value
from fetch_data import FetchError, get_json, require_key


def fetch_all_county_acreage():
    print("Fetching bearing orange acreage for every Florida county (Census years)...")
    records = []
    for year in CENSUS_YEARS:
        params = {
            "key": require_key("NASS_KEY"), "commodity_desc": "ORANGES", "state_alpha": "FL",
            "agg_level_desc": "COUNTY", "source_desc": "CENSUS", "year": year,
            "statisticcat_desc": "AREA BEARING", "unit_desc": "ACRES",
            "class_desc": "ALL CLASSES", "domain_desc": "TOTAL", "format": "json",
        }
        rows = get_json("https://quickstats.nass.usda.gov/api/api_GET/", params).get("data", [])
        if not rows:
            raise FetchError(f"NASS returned no county acreage for {year}")
        for row in rows:
            acres, status = parse_acreage_value(row.get("Value", ""), f"{row.get('county_name')} {year}")
            records.append({"county_name": row["county_name"].title(), "year": int(year),
                            "bearing_acres": acres, "status": status})
        time.sleep(0.2)
    df = pd.DataFrame(records)
    if df.duplicated(["county_name", "year"]).any():
        raise FetchError("NASS returned more than one ALL CLASSES total for a county-year")
    return df.sort_values(["year", "bearing_acres"], ascending=[True, False]).reset_index(drop=True)


def main():
    try:
        df = fetch_all_county_acreage()
    except FetchError as e:
        print(f"[FAILED] {e}\nNothing was written.")
        sys.exit(1)
    df.to_csv("data/census_orange_acres_by_county.csv", index=False)
    print(f"[OK] Saved data/census_orange_acres_by_county.csv ({len(df)} rows)")
    for year in (2017, 2022):
        top = df[(df.year == year) & (df.status == "published")].head(6)
        print(f"\nLargest published totals, {year}:")
        print(top[["county_name", "bearing_acres"]].to_string(index=False))
        print("withheld:", ", ".join(df[(df.year == year) & (df.status == "withheld")].county_name))


if __name__ == "__main__":
    main()
