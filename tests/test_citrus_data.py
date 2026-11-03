"""Tests for the US citrus-by-state helpers and the committed data."""

import numpy as np
import pandas as pd
import pytest

import citrus_data as cd


def rows(fruit, state, measure, values, start=2000, note=None):
    return [{"fruit": fruit, "state": state, "year": start + i, "measure": measure, "value": v,
             "note": "" if pd.notna(v) else "withheld (D)", "status": "reported"} for i, v in enumerate(values)]


def frame(*groups):
    return pd.DataFrame([r for g in groups for r in g])


# --- totals never hide a gap ---------------------------------------------------

def test_total_is_blank_when_a_component_is_withheld():
    df = frame(rows("Oranges", "FL", "bearing_acres", [100, 100, 100]),
               rows("Lemons", "CA", "bearing_acres", [10, np.nan, 10]))
    total = cd.complete_total(df, "bearing_acres")
    assert total.loc[2000] == 110 and total.loc[2002] == 110
    assert pd.isna(total.loc[2001])          # lemons withheld in 2001: no total, not 100


def test_year_with_no_row_inside_a_series_range_is_a_gap():
    df = frame(rows("Oranges", "FL", "bearing_acres", [100, 100, 100]),
               rows("Oranges", "TX", "bearing_acres", [5, 5], start=2000)
               + rows("Oranges", "TX", "bearing_acres", [5], start=2002))   # no 2001 row would be a gap
    df = df[~((df.state == "TX") & (df.year == 2001))]
    total = cd.complete_total(df, "bearing_acres")
    assert pd.isna(total.loc[2001]) and total.loc[2000] == 105


def test_ended_and_not_yet_started_series_are_not_part_of_the_total():
    df = frame(rows("Oranges", "FL", "bearing_acres", [100] * 4),
               rows("Oranges", "AZ", "bearing_acres", [10, 10], start=2000),     # ends 2001
               rows("Lemons", "FL", "bearing_acres", [7, 7], start=2002))         # starts 2002
    total = cd.complete_total(df, "bearing_acres")
    assert total.loc[2001] == 110 and total.loc[2002] == 107 and total.loc[2003] == 107


def test_total_by_group_masks_the_whole_year():
    df = frame(rows("Oranges", "FL", "bearing_acres", [100, 100]),
               rows("Lemons", "CA", "bearing_acres", [10, np.nan]))
    by_state = cd.complete_total(df, "bearing_acres", by="state")
    assert by_state.loc[2000, "FL"] == 100 and by_state.loc[2000, "CA"] == 10
    assert by_state.loc[2001].isna().all()    # a stacked chart must not show a partial stack


def test_incomplete_years_and_year_ranges():
    df = frame(rows("Oranges", "FL", "value_of_production_usd", [1, np.nan, np.nan, 1, np.nan]))
    bad = cd.incomplete_years(df, "value_of_production_usd")
    assert bad == [2001, 2002, 2004] and cd.year_ranges(bad) == "2001-2002, 2004"


# --- yield cross-check ------------------------------------------------------------

def test_conflicting_yield_is_flagged_and_blanked_without_changing_the_data():
    df = frame(rows("Oranges", "CA", "bearing_acres", [100, 100, 100]),
               rows("Oranges", "CA", "production_boxes", [30000, 31000, 30500]),
               rows("Oranges", "CA", "yield_boxes_per_acre", [300, 58, 305]))
    bad = cd.yield_conflicts(df)
    assert list(bad["year"]) == [2001] and bad["implied"].iloc[0] == pytest.approx(310)
    blanked = cd.blank_conflicts(df)
    pick = lambda d: d[(d.measure == "yield_boxes_per_acre") & (d.year == 2001)].value.item()
    assert pd.isna(pick(blanked)) and pick(df) == 58       # the original is untouched


# --- the committed data ---------------------------------------------------------------

def test_committed_data_has_one_row_per_series_year_and_marks_2026_preliminary():
    df = cd.load_citrus()
    assert not df.duplicated(["fruit", "state", "measure", "year"]).any()
    assert set(df["state"]) == {"AZ", "CA", "FL", "TX"}
    assert (df.loc[df["year"] == df["year"].max(), "status"] == "preliminary").all()
    assert (df.loc[df["year"] < df["year"].max(), "status"] == "reported").all()
    assert (df.loc[df["value"].isna(), "note"] != "").all()          # every blank says why


def test_the_only_conflicting_yield_in_the_committed_data_is_california_oranges_2022():
    bad = cd.yield_conflicts(cd.load_citrus())
    assert [(r.fruit, r.state, r.year) for r in bad.itertuples()] == [("Oranges", "CA", 2022)]
    assert bad["published"].iloc[0] == 58 and 270 < bad["implied"].iloc[0] < 300
    assert ("Oranges", "CA", 2022) in cd.CONFLICT_CITATIONS


def test_florida_orange_acreage_and_yield_match_the_known_series():
    df = cd.load_citrus()
    fl = df[(df.fruit == "Oranges") & (df.state == "FL")].pivot(index="year", columns="measure", values="value")
    assert fl.loc[2004, "yield_boxes_per_acre"] == 428 and fl.loc[2023, "yield_boxes_per_acre"] == 57
