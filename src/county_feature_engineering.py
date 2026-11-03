"""
Per-county weather features for four large Florida orange-producing counties:
Polk, Hendry, DeSoto, Highlands.

Runs the shared function in feature_engineering.py once per county on that
county's single primary NOAA station (src/fetch_county_data.py), so each series
describes that station, not the whole county. Real bearing acreage (Census
years only) is merged in alongside, and a per-station frost summary is written
for the map.

Missing weather is missing, never zero: a feature is blank (NA) when too many
days of its window have no observation. See feature_engineering.py.

This is explicitly NOT a county yield model: QuickStats has no county-level
orange yield or production in any year or source (verified against the API,
including the Census of Agriculture; see docs/API_SOURCES.md). No yield number
is estimated or interpolated here.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from feature_engineering import engineer_weather_features, station_availability_report
from fetch_data import START_YEAR, END_YEAR

Path("data").mkdir(exist_ok=True)

WEATHER_FEATURES = [
    "tmax_mean_grow", "tmin_mean_grow", "frost_days_bloom", "precip_total_grow",
    "precip_rolling_30", "precip_rolling_60", "precip_rolling_90",
    "temp_variance_grow", "gdd_total_grow",
]


def load_data():
    df_weather = pd.read_csv("data/county_weather.csv")
    df_acreage = pd.read_csv("data/county_acreage.csv")
    return df_weather, df_acreage


def frost_summary(df_features):
    """Per-station bloom-season frost summary, counting only years with a complete winter.

    A year counts only if every Jan-Mar night was observed, so stations have
    different numbers of counted years; `years_counted` and the first and last
    counted year are reported so averages are not read as if coverage were equal.
    The trend is a straight-line fit through the counted years, in frost days
    per decade; with few counted years it is a rough description, not a test.
    """
    rows = []
    for county, g in df_features.groupby("county_name"):
        ok = g.dropna(subset=["frost_days_bloom"]).copy()
        ok["frost"] = ok["frost_days_bloom"].astype(float)
        peak = ok.loc[ok["frost"].idxmax()] if len(ok) else None
        rows.append({
            "county_name": county,
            "years_in_range": len(g),
            "years_counted": len(ok),
            "first_year_counted": int(ok["year"].min()) if len(ok) else None,
            "last_year_counted": int(ok["year"].max()) if len(ok) else None,
            "mean_frost_days": round(float(ok["frost"].mean()), 2) if len(ok) else None,
            "max_frost_days": int(peak["frost"]) if peak is not None else None,
            "max_frost_year": int(peak["year"]) if peak is not None else None,
            "trend_days_per_decade": round(float(np.polyfit(ok["year"], ok["frost"], 1)[0] * 10), 2) if len(ok) > 2 else None,
        })
    return pd.DataFrame(rows)


def main():
    print("=" * 60)
    print("PER-COUNTY FEATURE ENGINEERING")
    print("=" * 60)

    df_weather, df_acreage = load_data()
    print(f"\n[OK] Loaded weather: {len(df_weather)} records")
    print(f"[OK] Loaded acreage: {len(df_acreage)} records")

    counties = df_weather["county_name"].unique()
    all_features = []

    for county in counties:
        county_weather = df_weather[df_weather["county_name"] == county]
        years = range(START_YEAR, END_YEAR + 1)
        station_availability_report(county_weather, county, years)
        feats = engineer_weather_features(county_weather, county, years)
        # Precip deviation from this county's own mean (years with missing rain are skipped)
        feats["precip_deviation"] = feats["precip_total_grow"] - feats["precip_total_grow"].mean()
        all_features.append(feats)
        n_missing = int(feats[WEATHER_FEATURES].isna().any(axis=1).sum())
        print(f"  [OK] {county}: {len(feats)} years engineered ({n_missing} with at least one missing feature)")

    df_features = pd.concat(all_features, ignore_index=True).sort_values(["county_name", "year"])

    # Merge in real acreage (Census years only). bearing_acres is blank when
    # USDA withheld the total, and in non-Census years; acreage_status tells
    # them apart ("published" / "withheld" / blank for non-Census years).
    # Nothing is interpolated or estimated: that would be a modeled value
    # presented next to real ones.
    acreage = df_acreage[["county_name", "year", "bearing_acres", "status"]].rename(
        columns={"status": "acreage_status"})
    df_final = df_features.merge(acreage, on=["county_name", "year"], how="left")

    df_final.to_csv("data/county_features.csv", index=False)
    print(f"\n[OK] Saved: data/county_features.csv ({len(df_final)} rows)")

    summary = frost_summary(df_features)
    summary.to_csv("data/station_frost_summary.csv", index=False)
    print(f"[OK] Saved: data/station_frost_summary.csv ({len(summary)} stations)")

    print("\n" + "=" * 60)
    print("BLOOM-SEASON FROST BY STATION (complete winters only)")
    print("=" * 60)
    print(summary.to_string(index=False))

    print("\nMissing (NA) values per feature, out of", len(df_final), "county-years:")
    print(df_final[WEATHER_FEATURES + ["precip_deviation"]].isna().sum().to_string())

    print("\n" + "=" * 60)
    print("Bearing acreage trend (real Census years, all counties)")
    print("=" * 60)
    acreage_pivot = df_final[df_final["bearing_acres"].notna()].pivot(
        index="year", columns="county_name", values="bearing_acres"
    )
    print(acreage_pivot.to_string())


if __name__ == "__main__":
    main()
