"""
Calculate the climate stress indicator for Florida orange yields.

The score is a weighted sum of four terms (weights 0.4 / 0.3 / 0.2 / 0.1):
bloom-season frost days, growing-season precipitation deviation, inverse
growing degree days, and a flag for the SAME year's yield being below the
25th percentile. It is an unvalidated heuristic, and the yield flag means it
is not a pure weather measure.
"""

import pandas as pd
import numpy as np
from pathlib import Path

Path("results").mkdir(exist_ok=True)


def calculate_stress_indicator(df):
    """
    Calculate composite stress score based on:
    - Frost days during bloom (Jan-Mar)
    - Precipitation deviation from normal (growing season)
    - GDD relative to historical mean
    - Whether this year's yield is below the 25th percentile (same year, not lagged)
    """

    df_stress = df.copy()

    # Historical percentiles/means (for 1990-2020 period)
    hist_period = df[df['year'] <= 2020]

    frost_p75 = hist_period['frost_days_bloom'].quantile(0.75)
    precip_std = hist_period['precip_deviation'].std()
    gdd_mean = hist_period['gdd_total_grow'].mean()
    yield_p25 = hist_period['yield_lbs_acre'].quantile(0.25)

    # Avoid division by zero (frost_p75 is 0 in a series where most winters have no frost)
    if frost_p75 == 0:
        frost_p75 = 1
    if precip_std == 0:
        precip_std = 1
    if gdd_mean == 0:
        gdd_mean = 1

    # Composite stress score
    stress_frost = (df_stress['frost_days_bloom'] / frost_p75).clip(0, 2)  # Cap at 2
    stress_precip = (df_stress['precip_deviation'].abs() / precip_std).clip(0, 2)
    stress_gdd = (gdd_mean / df_stress['gdd_total_grow']).clip(0.5, 2)  # Inverse GDD (low GDD = stress)
    stress_yield = (df_stress['yield_lbs_acre'] < yield_p25).astype(float)

    df_stress['stress_score'] = (
        0.4 * stress_frost +
        0.3 * stress_precip +
        0.2 * stress_gdd +
        0.1 * stress_yield
    )

    # Stress level categories
    def classify_stress(score):
        if score > 1.0:
            return 'HIGH'
        elif score > 0.5:
            return 'MODERATE'
        else:
            return 'LOW'

    df_stress['stress_level'] = df_stress['stress_score'].apply(classify_stress)

    return df_stress


def main():
    print("=" * 60)
    print("CLIMATE STRESS INDICATOR")
    print("=" * 60)

    df = pd.read_csv("data/df_model.csv")
    print(f"\n[OK] Loaded {len(df)} records")

    df_stress = calculate_stress_indicator(df)
    df_stress.to_csv("results/stress_indicator.csv", index=False)

    print(f"[OK] Calculated stress scores")
    print(f"[OK] Saved: results/stress_indicator.csv")

    # Summary
    print("\n" + "=" * 60)
    print("STRESS SUMMARY")
    print("=" * 60)
    print(f"\nStress level distribution:")
    print(df_stress['stress_level'].value_counts().to_string())

    print(f"\n\nRecent years (2020-2024):")
    recent = df_stress[df_stress['year'] >= 2020][['year', 'yield_lbs_acre', 'stress_score', 'stress_level']]
    print(recent.to_string(index=False))

    print("\n" + "=" * 60)
    print("Next: python run_dashboard.py to view the Dash app")
    print("=" * 60)


if __name__ == "__main__":
    main()
