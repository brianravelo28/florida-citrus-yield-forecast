"""
Per-county feature engineering for Florida's top 4 citrus counties by
bearing acreage: Polk, Hendry, DeSoto, Highlands.

Produces the same weather-derived features as feature_engineering.py
(frost days, GDD, precip patterns, thermal stability), calculated
separately per county from each county's own real local weather stations
(src/fetch_county_data.py). Real bearing acreage (Census years only) is
merged in alongside.

This is explicitly NOT a per-county yield model: NASS does not publish
county-level citrus YIELD or PRODUCTION in any year or source (verified
directly against the API, including the Census of Agriculture - see
docs/SCHEMA.md). No yield number is fabricated or interpolated here.
The output is a "local indicators" panel: real weather-driven stress
signals plus real acreage trends, per county, nothing more.
"""

import pandas as pd
import numpy as np
from pathlib import Path

Path("data").mkdir(exist_ok=True)


def load_data():
    df_weather = pd.read_csv("data/county_weather.csv")
    df_acreage = pd.read_csv("data/county_acreage.csv")
    return df_weather, df_acreage


def engineer_county_weather_features(df_weather, county_label):
    """Same feature set/logic as feature_engineering.py, scoped to one county."""
    county_df = df_weather[df_weather["county_name"] == county_label].copy()
    county_df["date"] = pd.to_datetime(county_df["date"])
    county_df["year"] = county_df["date"].dt.year
    county_df["month"] = county_df["date"].dt.month

    pivot = county_df.pivot_table(
        index=["year", "date"], columns="datatype", values="value", aggfunc="mean"
    ).reset_index()
    pivot.columns.name = None
    pivot["month"] = pivot["date"].dt.month

    # units=standard from NOAA CDO v2 -> TMAX/TMIN already in F, PRCP in inches
    pivot["TMAX_F"] = pivot.get("TMAX", pd.Series(dtype=float))
    pivot["TMIN_F"] = pivot.get("TMIN", pd.Series(dtype=float))
    pivot["PRCP"] = pivot.get("PRCP", pd.Series(dtype=float)).fillna(0) * 25.4  # inches to mm

    features_by_year = []
    for year in pivot["year"].unique():
        year_data = pivot[pivot["year"] == year].copy()

        bloom = year_data[(year_data["month"] >= 1) & (year_data["month"] <= 3)]
        frost_days = len(bloom[bloom["TMIN_F"] <= 32])

        grow = year_data[(year_data["month"] >= 5) & (year_data["month"] <= 8)]
        if len(grow) == 0:
            continue

        tmax_mean = grow["TMAX_F"].mean()
        tmin_mean = grow["TMIN_F"].mean()
        precip_total = grow["PRCP"].sum()
        temp_variance = grow["TMAX_F"].std()
        gdd = ((grow["TMAX_F"] + grow["TMIN_F"]) / 2 - 50).clip(lower=0).sum()

        precip_rolling_30 = grow["PRCP"].rolling(window=30).sum().max()
        precip_rolling_60 = grow["PRCP"].rolling(window=60).sum().max()
        precip_rolling_90 = grow["PRCP"].rolling(window=90).sum().max()

        features_by_year.append({
            "county_name": county_label,
            "year": int(year),
            "tmax_mean_grow": tmax_mean,
            "tmin_mean_grow": tmin_mean,
            "frost_days_bloom": frost_days,
            "precip_total_grow": precip_total,
            "precip_rolling_30": precip_rolling_30,
            "precip_rolling_60": precip_rolling_60,
            "precip_rolling_90": precip_rolling_90,
            "temp_variance_grow": temp_variance if not pd.isna(temp_variance) else 0,
            "gdd_total_grow": gdd,
        })

    return pd.DataFrame(features_by_year)


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
        feats = engineer_county_weather_features(df_weather, county)
        # Precip deviation from this county's own 1990-2024 mean
        precip_mean = feats["precip_total_grow"].mean()
        feats["precip_deviation"] = feats["precip_total_grow"] - precip_mean
        all_features.append(feats)
        print(f"  [OK] {county}: {len(feats)} years engineered")

    df_features = pd.concat(all_features, ignore_index=True).sort_values(["county_name", "year"])

    # Merge in real acreage (Census years only - left as NaN elsewhere,
    # not interpolated, since interpolation would be a modeled value
    # presented next to real ones without a clear label)
    df_final = df_features.merge(df_acreage[["county_name", "year", "bearing_acres"]],
                                   on=["county_name", "year"], how="left")

    df_final.to_csv("data/county_features.csv", index=False)
    print(f"\n[OK] Saved: data/county_features.csv ({len(df_final)} rows)")

    print("\n" + "=" * 60)
    print("SCHEMA")
    print("=" * 60)
    print(f"Columns: {list(df_final.columns)}")
    print(f"\nYears per county:")
    print(df_final.groupby("county_name")["year"].agg(["min", "max", "count"]))

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
