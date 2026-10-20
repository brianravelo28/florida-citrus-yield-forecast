"""
Feature engineering: merge yield and weather data, build the 12 model input features plus the target (log yield).

Missing weather is missing, never zero. Each feature covers a fixed window
(Jan-Mar bloom, May-Aug growing season). Frost days need every night of the
bloom window observed. Growing-season features need at least 95% of that
window's days observed and are computed from the observed days (nothing is
filled in or scaled up); otherwise they are left blank (NA). The station
set is fixed: a day counts as observed only if EVERY
station in the input reported the needed variable that day, so the series
means the same thing in every year (an earlier version averaged whichever
stations happened to report, and its membership changed by year). Frost
counts are strict because a missing night may have been a frost; rolling
windows only use runs of consecutive observed days. The bloom_days_missing
and grow_days_missing columns record how many days each window lacked.
"""

import numpy as np
import pandas as pd
from pathlib import Path

Path("data").mkdir(exist_ok=True)

STATEWIDE_LABEL = "Florida (Statewide)"
ROLLING_WINDOWS = (30, 60, 90)
MM_PER_INCH = 25.4
FROST_F = 32      # standard citrus freeze threshold
GDD_BASE_F = 50   # growing degree day base temperature
# Growing-season features need at least this share of the window's days observed.
# A practical cutoff, not a statistical standard; frost days still need every night.
MIN_GROW_COVERAGE = 0.95


def load_data():
    """Load raw NASS and NOAA data."""
    df_yield = pd.read_csv("data/nass_yield.csv")
    df_weather = pd.read_csv("data/noaa_weather.csv")
    return df_yield, df_weather


def station_availability_report(df_weather, label=STATEWIDE_LABEL, years=None):
    """Print a warning for every station-year with no observations.

    Under the fixed-station-set rule, a year in which any station reported
    nothing has no usable features (NA). A single-station input is flagged
    too, since its series is only as representative as that one station.
    """
    w = df_weather.copy()
    w["year"] = pd.to_datetime(w["date"]).dt.year
    all_years = list(years) if years is not None else range(w["year"].min(), w["year"].max() + 1)
    stations = w.groupby("station_id")["station_name"].first()
    if len(stations) == 1:
        print(f"  [NOTE] {label}: single station ({stations.iloc[0]}); series describes that station only")
    for sid, name in stations.items():
        have = set(w.loc[w["station_id"] == sid, "year"])
        gone = [y for y in all_years if y not in have]
        if gone:
            print(f"  [WARN] {label}: {name} has no observations in {gone}; those years' features are NA")


def engineer_weather_features(df_weather, label=STATEWIDE_LABEL, years=None):
    """
    One row per year of weather features for one area (statewide or a county).

    Input is long-format daily station data (date, datatype, value) in the
    units NOAA returns with units=standard: TMAX/TMIN in F, PRCP in inches.
    Features with an incomplete window are NaN (frost_days_bloom is
    nullable-integer <NA>). Pass `years` to get a row (all NA if there is no
    data) for every year in that range, not only years with observations.
    """
    w = df_weather.copy()
    w["date"] = pd.to_datetime(w["date"])

    # One row per date, stations averaged, but only on dates when every
    # station in the input reported the variable (fixed station set). Otherwise
    # the value stays NaN; it is never filled with 0 or from fewer stations.
    n_stations = w["station_id"].nunique()
    daily = w.pivot_table(index="date", columns="datatype", values="value", aggfunc="mean")
    reporting = w.groupby(["date", "datatype"])["station_id"].nunique().unstack()
    daily = daily.where(reporting.reindex(daily.index) >= n_stations)
    daily = daily.reindex(columns=["TMAX", "TMIN", "PRCP"])
    daily["PRCP"] = daily["PRCP"] * MM_PER_INCH  # inches to mm

    nan = np.nan

    def enough(series):
        """Growing-season rule: at least MIN_GROW_COVERAGE of the window's days observed."""
        return bool(series.notna().mean() >= MIN_GROW_COVERAGE)

    rows = []
    for year in (sorted(years) if years is not None else sorted(daily.index.year.unique())):
        # Reindex to the full calendar window so missing days are explicit NaN.
        bloom = daily.reindex(pd.date_range(f"{year}-01-01", f"{year}-03-31"))
        grow = daily.reindex(pd.date_range(f"{year}-05-01", f"{year}-08-31"))

        tmax_ok, tmin_ok, prcp_ok = enough(grow["TMAX"]), enough(grow["TMIN"]), enough(grow["PRCP"])
        both = grow[["TMAX", "TMIN"]].dropna()
        gdd_ok = tmax_ok and tmin_ok and len(both) / len(grow) >= MIN_GROW_COVERAGE
        bloom_ok = bool(bloom["TMIN"].notna().all())  # frost days: every night must be observed

        row = {
            "county_name": label,
            "year": int(year),
            # Means and std use the observed days (not an estimate for the missing ones).
            "tmax_mean_grow": grow["TMAX"].mean() if tmax_ok else nan,
            "tmin_mean_grow": grow["TMIN"].mean() if tmin_ok else nan,
            "frost_days_bloom": int((bloom["TMIN"] <= FROST_F).sum()) if bloom_ok else pd.NA,
            # Sums cover observed days only (not scaled up): up to 5% low if days are missing.
            "precip_total_grow": grow["PRCP"].sum() if prcp_ok else nan,
        }
        # Largest rolling sum over windows of real, fully observed calendar days.
        for window in ROLLING_WINDOWS:
            row[f"precip_rolling_{window}"] = grow["PRCP"].rolling(window).sum().max() if prcp_ok else nan
        row["temp_variance_grow"] = grow["TMAX"].std() if tmax_ok else nan  # std of daily TMAX
        row["gdd_total_grow"] = (
            ((both["TMAX"] + both["TMIN"]) / 2 - GDD_BASE_F).clip(lower=0).sum() if gdd_ok else nan
        )
        # Data-quality columns: how many window days had no observation.
        row["bloom_days_missing"] = int(bloom["TMIN"].isna().sum())
        row["grow_days_missing"] = int(grow[["TMAX", "TMIN", "PRCP"]].isna().sum().max())
        rows.append(row)

    features = pd.DataFrame(rows)
    features["frost_days_bloom"] = features["frost_days_bloom"].astype("Int64")
    return features


def merge_and_finalize(df_yield, df_weather_features):
    """Merge yield and weather, engineer remaining features."""

    # Merge on (county, year)
    df_model = df_yield.merge(df_weather_features, on=['year', 'county_name'], how='left')

    # Sort by year
    df_model = df_model.sort_values('year').reset_index(drop=True)

    # Lag-1 yield for carryover effect
    df_model['yield_lag1'] = df_model['yield_lbs_acre'].shift(1)

    # Precip deviation from the mean over the whole series (years with missing rain are skipped)
    precip_mean = df_model['precip_total_grow'].mean()
    df_model['precip_deviation'] = df_model['precip_total_grow'] - precip_mean

    # Year numeric (for trend)
    df_model['year_numeric'] = df_model['year']

    # Log yield (target transformation for right-skew)
    df_model['log_yield'] = np.log1p(df_model['yield_lbs_acre'])

    # Select final columns
    final_columns = [
        'county_name', 'year', 'yield_lbs_acre',
        'tmax_mean_grow', 'tmin_mean_grow', 'frost_days_bloom',
        'precip_total_grow', 'precip_rolling_30', 'precip_rolling_60', 'precip_rolling_90',
        'temp_variance_grow', 'gdd_total_grow', 'precip_deviation',
        'yield_lag1', 'year_numeric', 'log_yield',
        'bloom_days_missing', 'grow_days_missing'
    ]

    df_model = df_model[final_columns]

    return df_model


def main():
    print("=" * 60)
    print("FEATURE ENGINEERING")
    print("=" * 60)

    df_yield, df_weather = load_data()
    print(f"\n[OK] Loaded yield: {len(df_yield)} records")
    print(f"[OK] Loaded weather: {len(df_weather)} records")

    station_availability_report(df_weather)
    df_weather_features = engineer_weather_features(df_weather)
    print(f"[OK] Engineered weather features: {len(df_weather_features)} records")

    df_model = merge_and_finalize(df_yield, df_weather_features)
    df_model.to_csv("data/df_model.csv", index=False)

    print(f"[OK] Merged & finalized: {len(df_model)} records")
    print(f"\n[OK] Saved: data/df_model.csv")

    print("\n" + "=" * 60)
    print("FINAL MODEL DATA SCHEMA")
    print("=" * 60)
    print(f"\nShape: {df_model.shape}")
    print(f"Columns: {list(df_model.columns)}")
    print(f"\nData types:\n{df_model.dtypes}")
    print(f"\nFirst 10 rows:")
    print(df_model.head(10).to_string(index=False))
    print(f"\nSummary statistics:")
    print(df_model.describe().to_string())

    print("\n" + "=" * 60)
    print("Next: Run src/train_models.py to fit ARIMA and LightGBM")
    print("=" * 60)


if __name__ == "__main__":
    main()
