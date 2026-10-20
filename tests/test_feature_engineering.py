"""Tests for the weather aggregation and the missing-data rules, on small fixtures."""

import math

import numpy as np
import pandas as pd
import pytest

import feature_engineering as fe
from fetch_county_data import FetchError, parse_acreage_value
from fetch_data import is_plausible
from station_coverage import build_matrix
from stress_indicator import calculate_stress_indicator


def make_weather(year=2001, stations=("A",), tmax=90.0, tmin=70.0, prcp_in=0.1, bloom_tmin=50.0,
                 drop=None):
    """Long-format daily data Jan 1 - Aug 31 for the given stations.

    `drop` is a list of (station, datatype, "YYYY-MM-DD") observations to leave out.
    """
    drop = set(drop or [])
    rows = []
    for day in pd.date_range(f"{year}-01-01", f"{year}-08-31"):
        in_bloom = day.month <= 3
        values = {"TMAX": tmax, "TMIN": bloom_tmin if in_bloom else tmin, "PRCP": prcp_in}
        for st in stations:
            for datatype, value in values.items():
                key = (st, datatype, day.strftime("%Y-%m-%d"))
                if key not in drop:
                    rows.append({"station_id": st, "station_name": st, "date": day.strftime("%Y-%m-%d"),
                                 "datatype": datatype, "value": value})
    return pd.DataFrame(rows)


def features(df, **kwargs):
    return fe.engineer_weather_features(df, **kwargs).iloc[0]


def dates(start, end):
    return list(pd.date_range(start, end).strftime("%Y-%m-%d"))


# --- frost days -------------------------------------------------------------

def test_frost_days_counts_nights_at_or_below_32f():
    df = make_weather(bloom_tmin=50.0)
    cold = df[(df.datatype == "TMIN") & (df.date.isin(["2001-01-10", "2001-01-11", "2001-02-03"]))].index
    df.loc[cold, "value"] = [32.0, 28.0, 33.0]  # 32 and 28 count, 33 does not
    assert features(df)["frost_days_bloom"] == 2


def test_frost_is_na_when_any_bloom_night_is_missing():
    df = make_weather(drop=[("A", "TMIN", "2001-02-14")])
    assert pd.isna(features(df)["frost_days_bloom"])


# --- missing weather is missing, never zero -----------------------------------

def test_missing_rain_is_na_not_zero():
    df = make_weather(drop=[("A", "PRCP", d) for d in dates("2001-05-01", "2001-06-09")])  # 40 of 123 days
    assert pd.isna(features(df)["precip_total_grow"])


def test_growing_season_tolerates_up_to_five_percent_missing():
    df = make_weather(prcp_in=0.1, drop=[("A", "PRCP", d) for d in dates("2001-06-01", "2001-06-06")])  # 6 of 123
    row = features(df)
    assert not pd.isna(row["precip_total_grow"])
    # The sum covers the 117 observed days only; it is not scaled up to 123 days.
    assert row["precip_total_grow"] == pytest.approx(117 * 0.1 * fe.MM_PER_INCH)


def test_growing_season_is_na_beyond_five_percent_missing():
    df = make_weather(drop=[("A", "TMAX", d) for d in dates("2001-06-01", "2001-06-07")])  # 7 of 123
    row = features(df)
    assert pd.isna(row["tmax_mean_grow"]) and pd.isna(row["gdd_total_grow"])
    assert not pd.isna(row["tmin_mean_grow"])  # other variables are judged separately


def test_mean_uses_observed_days_only():
    df = make_weather(tmax=90.0)
    df.loc[(df.datatype == "TMAX") & (df.date == "2001-07-04"), "value"] = 100.0
    drop = df[(df.datatype == "TMAX") & (df.date.isin(["2001-07-05", "2001-07-06"]))].index
    row = features(df.drop(index=drop))
    assert row["tmax_mean_grow"] == pytest.approx((120 * 90.0 + 100.0) / 121)


def test_days_missing_columns():
    df = make_weather(drop=[("A", "TMIN", "2001-02-14"), ("A", "PRCP", "2001-07-01"), ("A", "PRCP", "2001-07-02")])
    row = features(df)
    assert row["bloom_days_missing"] == 1 and row["grow_days_missing"] == 2


# --- fixed station set --------------------------------------------------------

def test_day_needs_every_station():
    both_cold = make_weather(stations=("A", "B"), bloom_tmin=30.0)
    assert features(both_cold)["frost_days_bloom"] == 90

    # B misses one night: that night cannot be judged from A alone, so frost is NA
    one_missing = make_weather(stations=("A", "B"), bloom_tmin=30.0, drop=[("B", "TMIN", "2001-01-05")])
    assert pd.isna(features(one_missing)["frost_days_bloom"])


def test_stations_are_averaged_per_day():
    df = make_weather(stations=("A", "B"), tmax=90.0)
    df.loc[(df.station_id == "B") & (df.datatype == "TMAX"), "value"] = 100.0
    assert features(df)["tmax_mean_grow"] == pytest.approx(95.0)


def test_years_without_data_still_get_a_row_of_na():
    out = fe.engineer_weather_features(make_weather(2001), "X", years=range(2000, 2003))
    assert list(out["year"]) == [2000, 2001, 2002]
    assert out.loc[out.year == 2000, ["tmax_mean_grow", "gdd_total_grow", "frost_days_bloom"]].isna().all(axis=None)
    assert not out.loc[out.year == 2001, "tmax_mean_grow"].isna().item()


def test_availability_report_warns_about_absent_station_years(capsys):
    df = pd.concat([make_weather(2000, ("A", "B")), make_weather(2001, ("A",))])
    fe.station_availability_report(df)
    assert "B has no observations in [2001]" in capsys.readouterr().out


# --- derived features -----------------------------------------------------------

def test_gdd_uses_base_50_and_clips_at_zero():
    assert features(make_weather(tmax=90.0, tmin=70.0))["gdd_total_grow"] == pytest.approx((80 - 50) * 123)
    assert features(make_weather(tmax=60.0, tmin=30.0))["gdd_total_grow"] == 0.0  # mean 45 < base 50


def test_rolling_rain_windows_use_consecutive_observed_days():
    mm = 0.1 * fe.MM_PER_INCH
    flat = features(make_weather(prcp_in=0.1))
    assert flat["precip_rolling_30"] == pytest.approx(30 * mm)
    assert flat["precip_rolling_90"] == pytest.approx(90 * mm)

    # One missing day mid-season: windows containing it are skipped, not shortened
    gap = features(make_weather(prcp_in=0.1, drop=[("A", "PRCP", "2001-06-30")]))
    assert gap["precip_rolling_30"] == pytest.approx(30 * mm)


def test_temp_variance_grow_is_a_standard_deviation():
    df = make_weather(tmax=90.0)
    df.loc[(df.datatype == "TMAX") & (df.date <= "2001-06-30"), "value"] = 80.0
    tmax = pd.Series([80.0] * 61 + [90.0] * 62)  # May 1 - Jun 30, then Jul 1 - Aug 31
    assert features(df)["temp_variance_grow"] == pytest.approx(tmax.std())


# --- data hygiene ---------------------------------------------------------------

def test_plausibility_filter_bounds():
    assert is_plausible("TMAX", 110.0) and not is_plausible("TMAX", 115.0)
    assert is_plausible("TMIN", -5.0) and not is_plausible("TMIN", 101.0)
    assert is_plausible("PRCP", 0.0) and not is_plausible("PRCP", -0.1)


def test_withheld_acreage_stays_blank():
    acres, status = parse_acreage_value(" (D)", "Hendry 2002")
    assert status == "withheld" and math.isnan(acres)
    assert parse_acreage_value("54,692", "Polk 2022") == (54692.0, "published")
    with pytest.raises(FetchError):
        parse_acreage_value("oops", "Polk 2022")


def test_committed_county_acreage_has_blank_withheld_rows():
    df = pd.read_csv("data/county_acreage.csv")
    withheld = df[df["status"] == "withheld"]
    assert len(withheld) == 4 and withheld["bearing_acres"].isna().all()
    assert df.loc[df["status"] == "published", "bearing_acres"].notna().all()


def test_station_coverage_matrix_counts_window_days():
    rows = [{"station_name": "S", "station_id": "x", "year": 2001, "month": m, "datatype": "TMIN", "days": d}
            for m, d in ((1, 31), (2, 28), (3, 31))]
    rows += [{"station_name": "S", "station_id": "x", "year": 2001, "month": m, "datatype": dt, "days": 31}
             for m in (5, 6, 7, 8) for dt in ("TMAX", "TMIN", "PRCP")]
    m = build_matrix(pd.DataFrame(rows))
    row = m[(m.station == "S") & (m.year == 2001)].iloc[0]
    assert row["bloom_tmin_days"] == 90 and row["bloom_days_needed"] == 90
    assert row["grow_tmax_days"] == 124 and row["grow_prcp_days"] == 124


# --- stress indicator -----------------------------------------------------------

def test_stress_levels_follow_thresholds():
    df = pd.DataFrame({
        "year": range(1990, 2000), "frost_days_bloom": [0] * 9 + [10],
        "precip_deviation": [0.0] * 9 + [500.0], "gdd_total_grow": [4000.0] * 10,
        "yield_lbs_acre": [20000.0] * 10,
    })
    out = calculate_stress_indicator(df)
    assert out["stress_level"].iloc[-1] == "HIGH"
    assert out["stress_level"].iloc[0] in ("LOW", "MODERATE")
    assert np.isfinite(out["stress_score"]).all()
