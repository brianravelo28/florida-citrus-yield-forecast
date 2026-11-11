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


# --- NASS's own state totals fill the years the fruit values leave blank -------------

def totals_rows(state, measure, values, start=2000):
    return [{"state": state, "year": start + i, "measure": measure, "value": v, "note": "", "status": "reported"}
            for i, v in enumerate(values)]


def test_published_totals_replace_the_sum_only_where_nass_publishes_them():
    fruit = frame(rows("Oranges", "FL", "bearing_acres", [100, 100, 100, 100]),
                  rows("Lemons", "CA", "bearing_acres", [10, 10, np.nan, 10]))            # lemons withheld in 2002
    totals = pd.DataFrame(totals_rows("FL", "bearing_acres", [100, 100], start=2002)
                          + totals_rows("CA", "bearing_acres", [12, 10], start=2002))     # NASS publishes 2002-2003
    total = cd.combined_total(fruit, totals, "bearing_acres")
    assert total.loc[2000] == 110 and total.loc[2001] == 110     # before NASS's series: the sum of the fruit values
    assert total.loc[2002] == 112                                # withheld at fruit level, published in the total
    assert total.loc[2003] == 110
    by_state = cd.combined_total(fruit, totals, "bearing_acres", by="state")
    assert by_state.loc[2002, "CA"] == 12 and by_state.loc[2001, "CA"] == 10
    assert cd.combined_total(fruit, totals, "bearing_acres", state="CA").loc[2002] == 12


def test_a_year_with_neither_a_complete_sum_nor_a_published_total_stays_blank():
    fruit = frame(rows("Oranges", "FL", "bearing_acres", [100, 100, 100]),
                  rows("Lemons", "CA", "bearing_acres", [10, np.nan, 10]))
    totals = pd.DataFrame(totals_rows("FL", "bearing_acres", [100], start=2002)
                          + totals_rows("CA", "bearing_acres", [10], start=2002))
    total = cd.combined_total(fruit, totals, "bearing_acres")
    assert pd.isna(total.loc[2001]) and cd.gap_years(total) == [2001]
    # a published total that covers only some states does not make a national total
    partial = pd.DataFrame(totals_rows("FL", "bearing_acres", [100], start=2001))
    assert pd.isna(cd.combined_total(fruit, partial, "bearing_acres").loc[2001])


def test_no_totals_for_a_measure_falls_back_to_the_complete_sum():
    fruit = frame(rows("Oranges", "FL", "bearing_acres", [100, 100]))
    totals = pd.DataFrame(totals_rows("FL", "value_of_production_usd", [1, 1]))
    assert cd.combined_total(fruit, totals, "bearing_acres").loc[2000] == 100


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


def test_committed_totals_file_is_one_row_per_state_year_and_measure():
    t = cd.load_totals()
    assert len(t) == 152 and not t.duplicated(["state", "year", "measure"]).any()
    assert set(t["state"]) == {"AZ", "CA", "FL", "TX"} and set(t["measure"]) == {"bearing_acres", "value_of_production_usd"}
    assert t["year"].min() == 2008 and t["year"].max() == cd.load_citrus()["year"].max()
    assert t["value"].notna().all() and t["note"].isna().all()          # NASS published every one; no suppression codes
    assert (t.loc[t["year"] == t["year"].max(), "status"] == "preliminary").all()
    assert (t.loc[t["year"] < t["year"].max(), "status"] == "reported").all()


def test_fruit_sums_agree_with_nass_state_totals_where_no_fruit_value_is_blank():
    df, t = cd.load_citrus(), cd.load_totals()
    off = []
    for measure in ("bearing_acres", "value_of_production_usd"):
        parts = df[df["measure"] == measure].groupby(["state", "year"])["value"].agg(total="sum", blanks=lambda s: s.isna().sum())
        m = t[t["measure"] == measure].merge(parts.reset_index(), on=["state", "year"])
        complete = m[m["blanks"] == 0]
        diff = (complete["total"] - complete["value"]).abs()
        off += [(measure, r.state, r.year) for r in complete[diff >= 1].itertuples()]
        assert (diff / complete["value"]).max() < 0.01                  # never more than 1% apart
        if measure == "bearing_acres":
            assert diff.max() == 0 and len(m) == 76                     # acres agree exactly in every state-year
    # the three state-years where the fruit values sum above NASS's own total (0.03% to 0.93%)
    assert sorted(off) == [("value_of_production_usd", "CA", 2018), ("value_of_production_usd", "FL", 2018),
                           ("value_of_production_usd", "FL", 2020)]


def test_with_nass_totals_the_us_series_have_one_gap_and_the_value_peak_is_2012():
    df, t = cd.load_citrus(), cd.load_totals()
    acres = cd.combined_total(df, t, "bearing_acres")
    value = cd.combined_total(df, t, "value_of_production_usd")
    assert cd.gap_years(acres) == []                                    # was 2010-2012 from the fruit sums alone
    assert cd.gap_years(value) == [1991]                                # was 1991 and 2009-2016; Texas has no 1991 value
    assert value.idxmax() == 2012 and value.loc[2012] == 3_712_817_000
    assert value.loc[2017] == pytest.approx(3_532_125_000) and value.loc[2026] == pytest.approx(3_148_286_000)
    by_state = cd.combined_total(df, t, "value_of_production_usd", by="state")
    assert cd.gap_years(by_state) == [1991]
    assert by_state.loc[2012].sum() == pytest.approx(value.loc[2012])    # the state totals add up to the US total
    # a stacked frame: whole blank years are gaps, a column blank because its series ended is not
    by_fruit = cd.complete_total(df, "value_of_production_usd", by="fruit")
    assert cd.gap_years(by_fruit) == [1991] + list(range(2009, 2017))


def test_florida_orange_acreage_and_yield_match_the_known_series():
    df = cd.load_citrus()
    fl = df[(df.fruit == "Oranges") & (df.state == "FL")].pivot(index="year", columns="measure", values="value")
    assert fl.loc[2004, "yield_boxes_per_acre"] == 428 and fl.loc[2023, "yield_boxes_per_acre"] == 57
