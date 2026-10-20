"""
Station sensitivity: how much do the statewide weather features and the
stress-indicator result depend on which stations feed the series?

Rebuilds the statewide features from data/noaa_weather.csv with the same
engineering code used for the model, once per station choice, and reports
frost days before and after 2008, the growing-season minimum-temperature
trend, years with NA features, and the HIGH-stress years. Writes
results/station_sensitivity.csv. Runs offline on the committed data.

The pre-change numbers (four stations averaged by whichever reported each
day) were produced by the earlier version of the pipeline and are recorded in
docs/METHODOLOGY.md for comparison; that version is not re-run here.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from feature_engineering import engineer_weather_features, merge_and_finalize
from stress_indicator import calculate_stress_indicator

Path("results").mkdir(exist_ok=True)

TAMPA = "USW00012842"
ARCHBOLD = "USC00080236"
CHOICES = {
    "Tampa + Archbold (used)": [TAMPA, ARCHBOLD],
    "Tampa only": [TAMPA],
    "Archbold only": [ARCHBOLD],
}


def summarize(df_weather, df_yield, station_ids):
    w = df_weather[df_weather["station_id"].isin(station_ids)]
    model = merge_and_finalize(df_yield, engineer_weather_features(w))
    frost = model["frost_days_bloom"].astype("float")
    ok = model.dropna(subset=["tmin_mean_grow"])
    trend = np.polyfit(ok["year"], ok["tmin_mean_grow"], 1)[0] * 10
    complete = model.dropna(subset=["frost_days_bloom", "tmax_mean_grow", "gdd_total_grow", "precip_deviation"])
    stressed = calculate_stress_indicator(complete)
    high = [int(y) for y in stressed.loc[stressed["stress_level"] == "HIGH", "year"]]
    return {
        "frost_mean_1990_2007": round(frost[model["year"] <= 2007].mean(), 2),
        "frost_mean_2008_2024": round(frost[model["year"] >= 2008].mean(), 2),
        "tmin_grow_trend_F_per_decade": round(trend, 2),
        "years_with_NA_features": int(model.drop(columns=["yield_lag1"]).isna().any(axis=1).sum()),
        "high_stress_years": " ".join(map(str, high)),
    }


def main():
    df_weather = pd.read_csv("data/noaa_weather.csv")
    df_yield = pd.read_csv("data/nass_yield.csv")
    rows = [{"station_set": name, **summarize(df_weather, df_yield, ids)} for name, ids in CHOICES.items()]
    out = pd.DataFrame(rows)
    out.to_csv("results/station_sensitivity.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
