"""
Feature engineering: merge yield and weather data, calculate 13 features.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path

Path("data").mkdir(exist_ok=True)


def load_data():
    """Load raw NASS and NOAA data."""
    df_yield = pd.read_csv("data/nass_yield.csv")
    df_weather = pd.read_csv("data/noaa_weather.csv")
    return df_yield, df_weather


def engineer_weather_features(df_weather):
    """
    Aggregate weather data by county-year.
    Calculate: tmax_mean, tmin_mean, frost_days, precip_total, rolling windows, gdd, temp_variance.
    """
    df_weather['date'] = pd.to_datetime(df_weather['date'])
    df_weather['year'] = df_weather['date'].dt.year
    df_weather['month'] = df_weather['date'].dt.month

    # Pivot weather data (TMAX, TMIN, PRCP as columns)
    weather_pivot = df_weather.pivot_table(
        index=['year', 'date'],
        columns='datatype',
        values='value',
        aggfunc='mean'
    ).reset_index()

    weather_pivot.columns.name = None
    weather_pivot['month'] = weather_pivot['date'].dt.month

    # Convert from tenths of mm and tenths of F to standard units
    weather_pivot['TMAX'] = (weather_pivot['TMAX'].fillna(0) / 10.0 - 32) * 5/9  # to Celsius
    weather_pivot['TMIN'] = (weather_pivot['TMIN'].fillna(0) / 10.0 - 32) * 5/9  # to Celsius
    weather_pivot['PRCP'] = weather_pivot['PRCP'].fillna(0) / 10.0  # to mm

    # Actually keep in Fahrenheit for citrus industry standards
    weather_pivot['TMAX_F'] = weather_pivot['TMAX'] * 9/5 + 32
    weather_pivot['TMIN_F'] = weather_pivot['TMIN'] * 9/5 + 32

    features_by_year = []

    for year in weather_pivot['year'].unique():
        year_data = weather_pivot[weather_pivot['year'] == year].copy()

        # Bloom season (Jan-Mar): frost days
        bloom = year_data[(year_data['month'] >= 1) & (year_data['month'] <= 3)]
        frost_days = len(bloom[bloom['TMIN_F'] <= 0])  # 32F = 0C

        # Growing season (May-Aug)
        grow = year_data[(year_data['month'] >= 5) & (year_data['month'] <= 8)]

        if len(grow) == 0:
            continue

        tmax_mean = grow['TMAX_F'].mean()
        tmin_mean = grow['TMIN_F'].mean()
        precip_total = grow['PRCP'].sum()
        temp_variance = grow['TMAX_F'].std()

        # GDD calculation (base 50F)
        gdd = ((grow['TMAX_F'] + grow['TMIN_F']) / 2 - 50).clip(lower=0).sum()

        # Rolling windows for precipitation
        precip_rolling_30 = grow['PRCP'].rolling(window=30).sum().max()
        precip_rolling_60 = grow['PRCP'].rolling(window=60).sum().max()
        precip_rolling_90 = grow['PRCP'].rolling(window=90).sum().max()

        features_by_year.append({
            'year': int(year),
            'county_name': 'Polk County',
            'tmax_mean_grow': tmax_mean,
            'tmin_mean_grow': tmin_mean,
            'frost_days_bloom': frost_days,
            'precip_total_grow': precip_total,
            'precip_rolling_30': precip_rolling_30,
            'precip_rolling_60': precip_rolling_60,
            'precip_rolling_90': precip_rolling_90,
            'temp_variance_grow': temp_variance if not pd.isna(temp_variance) else 0,
            'gdd_total_grow': gdd
        })

    return pd.DataFrame(features_by_year)


def merge_and_finalize(df_yield, df_weather_features):
    """Merge yield and weather, engineer remaining features."""

    # Merge on (county, year)
    df_model = df_yield.merge(df_weather_features, on=['year', 'county_name'], how='left')

    # Sort by year
    df_model = df_model.sort_values('year').reset_index(drop=True)

    # Lag-1 yield for carryover effect
    df_model['yield_lag1'] = df_model['yield_lbs_acre'].shift(1)

    # Precip deviation from 30-year mean
    precip_mean_30yr = df_model['precip_total_grow'].mean()
    df_model['precip_deviation'] = df_model['precip_total_grow'] - precip_mean_30yr

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
        'yield_lag1', 'year_numeric', 'log_yield'
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
