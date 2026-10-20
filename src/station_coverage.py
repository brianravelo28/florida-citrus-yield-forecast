"""
Station coverage probe: how many days of actual TMAX / TMIN / PRCP does each
candidate NOAA station report in each month of 1990-2024?

The NOAA station catalog's date ranges are not evidence of data (see
docs/API_SOURCES.md), so this requests real observations and counts the days
that pass the same plausibility filter the weather fetchers use. The output,
data/station_coverage.csv, has one row per station, year, month and datatype
(data/station_coverage_matrix.csv summarizes it per station-year), and is what the station-set choice in docs/METHODOLOGY.md is based on.

Needs NOAA_API_KEY (or NOAA_TOKEN) in the environment. Any failed request stops
the run and writes nothing.
"""

import sys
import time
from pathlib import Path

import pandas as pd

from fetch_data import FetchError, get_json, is_plausible, require_key, START_YEAR, END_YEAR

# Candidates found by listing GHCND stations with TMIN in Polk, Highlands,
# Hendry and DeSoto counties, plus the stations already in use.
CANDIDATES = {
    # Currently used (statewide / Polk)
    "Lakeland Linder": "USW00012883",
    "Tampa International": "USW00012842",
    "Orlando Executive": "USW00012841",
    "Sebring": "USW00092827",
    # Currently used (counties)
    "La Belle": "USC00084662",
    "Moore Haven Lock 1": "USC00085895",
    "Arcadia": "USC00080228",
    "Punta Gorda Airport": "USW00012812",
    "Avon Park 2 W": "USC00080369",
    # Polk candidates
    "Bartow 1 SE": "USC00080478",
    "Lake Alfred Exp Station": "USC00084707",
    "Lakeland 2": "USC00084802",
    "Mountain Lake": "USC00085973",
    "Winter Haven (co-op)": "USC00089707",
    "Winter Haven Gilbert Airport": "USW00012876",
    # Highlands candidates
    "Archbold Bio Station": "USC00080236",
    # Hendry candidates
    "Big Cypress": "USC00080737",
    "Clewiston": "USC00081654",
    "Clewiston No. 2": "USC00081651",
    "Devils Garden": "USC00082298",
}

URL = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"


def get_key():
    for name in ("NOAA_API_KEY", "NOAA_TOKEN"):
        try:
            return require_key(name)
        except FetchError:
            continue
    raise FetchError("Set NOAA_API_KEY (or NOAA_TOKEN) in the environment.")


def station_year_days(station_id, year, headers):
    """Return {(month, datatype): days with a plausible observation}."""
    seen = set()
    offset = 1
    while True:
        params = {
            "datasetid": "GHCND", "stationid": f"GHCND:{station_id}",
            "startdate": f"{year}-01-01", "enddate": f"{year}-12-31",
            "datatypeid": "TMAX,TMIN,PRCP", "units": "standard",
            "limit": 1000, "offset": offset,
        }
        data = get_json(URL, params, headers=headers)
        for rec in data.get("results", []):
            try:
                value = float(rec["value"])
            except (KeyError, ValueError, TypeError):
                continue
            if is_plausible(rec["datatype"], value):
                seen.add((rec["date"][:10], rec["datatype"]))
        total = data.get("metadata", {}).get("resultset", {}).get("count", 0)
        if offset + 1000 > total:
            break
        offset += 1000
        time.sleep(0.2)
    counts = {}
    for date, datatype in seen:
        key = (int(date[5:7]), datatype)
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_matrix(coverage):
    """Per station and year: days observed in the two feature windows.

    bloom = Jan-Mar TMIN (frost days); grow = May-Aug TMAX / TMIN / PRCP
    (the smallest of the three counts is reported).
    """
    def window_days(months, datatype):
        sel = coverage[coverage["month"].isin(months) & (coverage["datatype"] == datatype)]
        return sel.groupby(["station_name", "year"])["days"].sum()

    grow = {dt: window_days([5, 6, 7, 8], dt) for dt in ("TMAX", "TMIN", "PRCP")}
    bloom = window_days([1, 2, 3], "TMIN")
    rows = []
    for name in dict.fromkeys(coverage["station_name"]):
        for year in range(START_YEAR, END_YEAR + 1):
            rows.append({
                "station": name, "year": year,
                "bloom_tmin_days": int(bloom.get((name, year), 0)),
                "bloom_days_needed": 91 if year % 4 == 0 else 90,
                "grow_tmax_days": int(grow["TMAX"].get((name, year), 0)),
                "grow_tmin_days": int(grow["TMIN"].get((name, year), 0)),
                "grow_prcp_days": int(grow["PRCP"].get((name, year), 0)),
            })
    return pd.DataFrame(rows)


def main():
    if "--from-csv" in sys.argv:  # rebuild the matrix from the saved probe output
        build_matrix(pd.read_csv("data/station_coverage.csv")).to_csv("data/station_coverage_matrix.csv", index=False)
        print("[OK] Saved data/station_coverage_matrix.csv")
        return
    try:
        headers = {"token": get_key()}
        rows = []
        for name, sid in CANDIDATES.items():
            print(f"{name} ({sid})", flush=True)
            for year in range(START_YEAR, END_YEAR + 1):
                for (month, datatype), days in station_year_days(sid, year, headers).items():
                    rows.append({"station_name": name, "station_id": sid, "year": year,
                                 "month": month, "datatype": datatype, "days": days})
                time.sleep(0.2)
    except FetchError as e:
        print(f"[FAILED] {e}\nNothing was written.")
        sys.exit(1)

    Path("data").mkdir(exist_ok=True)
    coverage = pd.DataFrame(rows)
    coverage.to_csv("data/station_coverage.csv", index=False)
    build_matrix(coverage).to_csv("data/station_coverage_matrix.csv", index=False)
    print(f"[OK] Saved data/station_coverage.csv ({len(rows)} rows) and data/station_coverage_matrix.csv")


if __name__ == "__main__":
    main()
