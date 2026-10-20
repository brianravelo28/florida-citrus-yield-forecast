"""
Per-county feature engineering for four large Florida orange-producing
counties: Polk, Hendry, DeSoto, Highlands.

Produces the same weather-derived features as feature_engineering.py
(frost days, GDD, precip patterns, thermal stability) using the same shared
function, run separately per county on each county's own real local weather
stations (src/fetch_county_data.py). Real bearing acreage (Census years only)
is merged in alongside.

Missing weather is missing, never zero: a feature is blank (NA) when any day
of its window has no observation. See the module docstring of
feature_engineering.py.

This is explicitly NOT a per-county yield model: NASS does not publish
county-level citrus YIELD or PRODUCTION in any year or source (verified
directly against the API, including the Census of Agriculture - see
docs/SCHEMA.md). No yield number is fabricated or interpolated here.
The output is a "local indicators" panel: real weather-driven stress
signals plus real acreage trends, per county, nothing more.
"""

import pandas as pd
from pathlib import Path

from feature_engineering import engineer_weather_features

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
        feats = engineer_weather_features(df_weather[df_weather["county_name"] == county], county)
        # Precip deviation from this county's own 1990-2024 mean (years with missing rain are skipped)
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

    print("\n" + "=" * 60)
    print("SCHEMA")
    print("=" * 60)
    print(f"Columns: {list(df_final.columns)}")
    print(f"\nYears per county:")
    print(df_final.groupby("county_name")["year"].agg(["min", "max", "count"]))

    print("\nMissing (NA) values per feature, out of", len(df_final), "county-years:")
    print(df_final[WEATHER_FEATURES + ["precip_deviation"]].isna().sum().to_string())

    print("\n" + "=" * 60)
    print("2024 SNAPSHOT (most recent year, all counties)")
    print("=" * 60)
    snap = df_final[df_final["year"] == 2024][
        ["county_name", "frost_days_bloom", "tmax_mean_grow", "tmin_mean_grow",
         "precip_total_grow", "gdd_total_grow"]
    ]
    print(snap.to_string(index=False))

    print("\n" + "=" * 60)
    print("Bearing acreage trend (real Census years, all counties)")
    print("=" * 60)
    acreage_pivot = df_final[df_final["bearing_acres"].notna()].pivot(
        index="year", columns="county_name", values="bearing_acres"
    )
    print(acreage_pivot.to_string())


if __name__ == "__main__":
    main()
