"""Tests for the CPI fetch (mocked responses) and the constant-dollar adjustment."""

import numpy as np
import pandas as pd
import pytest

import citrus_data as cd
import fetch_cpi
from fetch_industry_data import FetchError


def point(year, month, value, footnote=None):
    return {"year": str(year), "period": f"M{month:02d}", "value": value,
            "footnotes": [{"text": footnote}] if footnote else [{}]}


def payload(points, status="REQUEST_SUCCEEDED"):
    return {"status": status, "message": [], "Results": {"series": [{"seriesID": "CUUR0000SA0", "data": points}]}}


def cpi_frame(start=(1989, 10), months=25, base=100.0, step=1.0, blank=()):
    """A synthetic monthly CPI file; `blank` lists (year, month) pairs BLS did not publish."""
    rows, (y, m) = [], start
    for i in range(months):
        v = np.nan if (y, m) in blank else base + step * i
        rows.append({"year": y, "month": m, "cpi": v, "note": "" if v == v else "not published"})
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return pd.DataFrame(rows)


# --- the fetch, against mocked BLS responses --------------------------------------------------

def test_parse_window_reads_months_skips_the_annual_average_and_keeps_an_unpublished_month_blank():
    pts = [point(2025, 9, "324.800"), point(2025, 10, "-", "Data unavailable due to the 2025 lapse in appropriations"),
           point(2025, 11, "324.122"), {"year": "2025", "period": "M13", "value": "321.9", "footnotes": [{}]}]
    rows = fetch_cpi.parse_window(payload(pts), "2019-2028")
    assert [(r["year"], r["month"]) for r in rows] == [(2025, 9), (2025, 10), (2025, 11)]     # no M13
    assert rows[0]["cpi"] == 324.8 and rows[2]["cpi"] == 324.122
    assert np.isnan(rows[1]["cpi"]) and "lapse in appropriations" in rows[1]["note"]


@pytest.mark.parametrize("bad", [
    payload([point(2024, 1, "300.0")], status="REQUEST_NOT_PROCESSED"),          # BLS says no, with HTTP 200
    {"status": "REQUEST_SUCCEEDED", "Results": {"series": []}},                  # success with no series
    payload([]),                                                                 # success with no data
    payload([point(2024, 1, "-"), point(2024, 2, "-")]),                         # nothing published
    payload([point(2024, 1, "abc")]),                                            # not a number
])
def test_a_bad_bls_response_stops_the_run(bad):
    with pytest.raises(FetchError):
        fetch_cpi.parse_window(bad, "test")


def test_build_cpi_assembles_windows_and_stops_on_a_missing_month(monkeypatch):
    def full(body):
        a, b = int(body["startyear"]), int(body["endyear"])
        return payload([point(y, m, f"{100 + (y - 1989) * 12 + m}") for y in range(a, min(b, 2026) + 1) for m in range(1, 13)])
    monkeypatch.setattr(fetch_cpi, "post_json", lambda url, body: full(body))
    df = fetch_cpi.build_cpi()
    assert (df.year.iloc[0], df.month.iloc[0]) == (1989, 10) and (df.year.iloc[-1], df.month.iloc[-1]) == (2026, 12)
    assert not df.duplicated(["year", "month"]).any()

    def hole(body):                                            # BLS drops January 2005 from its reply
        p = full(body)
        p["Results"]["series"][0]["data"] = [x for x in p["Results"]["series"][0]["data"] if not (x["year"] == "2005" and x["period"] == "M01")]
        return p
    monkeypatch.setattr(fetch_cpi, "post_json", lambda url, body: hole(body))
    with pytest.raises(FetchError):
        fetch_cpi.build_cpi()


# --- the constant-dollar adjustment ------------------------------------------------------------

def test_season_cpi_is_the_october_to_september_mean_and_blank_when_a_season_is_not_covered():
    cpi = cpi_frame(months=25)                                  # Oct 1989 .. Oct 1991, values 100, 101, ...
    s = cd.season_cpi(cpi)
    assert s.loc[1990] == pytest.approx(np.mean(range(100, 112)))        # Oct 1989 .. Sep 1990
    assert s.loc[1991] == pytest.approx(np.mean(range(112, 124)))        # Oct 1990 .. Sep 1991


def test_one_unpublished_month_is_tolerated_two_are_not_and_a_short_window_is_blank():
    one = cd.season_cpi(cpi_frame(months=25, blank={(1990, 3)}))
    assert one.loc[1990] == pytest.approx(np.mean([100 + i for i in range(12) if i != 5]))   # mean of the 11 published months
    assert np.isnan(cd.season_cpi(cpi_frame(months=25, blank={(1990, 3), (1990, 4)})).loc[1990])
    short = cd.season_cpi(cpi_frame(months=20))                  # the file ends in May 1991, mid-season
    assert not np.isnan(short.loc[1990]) and np.isnan(short.loc[1991])


def test_the_base_year_has_a_factor_of_one_and_real_dollars_equal_nominal_there():
    cpi = cpi_frame(months=37)
    f = cd.real_factors(cpi, base_year=1992)
    assert f.loc[1992] == 1.0 and f.loc[1990] > 1.0 > 0 and f.loc[1991] > 1.0   # earlier dollars are worth more in later prices
    nominal = pd.Series({1990: 100.0, 1992: 100.0}, name="v")
    real = cd.to_real(nominal, f)
    assert real.loc[1992] == 100.0 and real.loc[1990] == pytest.approx(100.0 * f.loc[1990])
    frame = pd.DataFrame({"a": nominal, "b": nominal * 2})
    assert cd.to_real(frame, f).loc[1992].tolist() == [100.0, 200.0]
    assert np.isnan(cd.to_real(pd.Series({2050: 1.0}), f).loc[2050])           # no CPI for that season: no real value


# --- the committed CPI file -----------------------------------------------------------------------

def test_committed_cpi_file_is_consecutive_months_with_one_published_gap_and_known_values():
    c = cd.load_cpi()
    months = c["year"] * 12 + c["month"] - 1
    assert (c.year.iloc[0], c.month.iloc[0]) == (1989, 10) and (months.diff().dropna() == 1).all()
    assert not c.duplicated(["year", "month"]).any()
    blank = c[c["cpi"].isna()]
    assert [(r.year, r.month) for r in blank.itertuples()] == [(2025, 10)]
    assert "lapse in appropriations" in blank["note"].iloc[0]
    assert c[c["cpi"].notna()]["note"].isna().all()
    value = lambda y, m: c[(c.year == y) & (c.month == m)].cpi.item()
    assert value(1990, 1) == 127.4 and value(2019, 12) == 256.974         # published CUUR0000SA0 values


def test_the_real_dollar_findings_quoted_in_the_readme():
    df, tot, f = cd.load_citrus(), cd.load_totals(), cd.real_factors(cd.load_cpi())
    series = lambda state=None: cd.combined_total(df, tot, "value_of_production_usd", state=state).dropna()
    us, us_real = series(), cd.to_real(series(), f)
    assert us.idxmax() == 2012 and round(us.max() / 1e9, 2) == 3.71                      # as reported: highest in 2012
    assert round((us.loc[2026] / us.max() - 1) * 100) == -15
    assert us_real.idxmax() == 1990 and round(us_real.max() / 1e9, 2) == 5.49            # constant dollars: highest in the first year
    assert round(us_real.loc[2026] / 1e9, 2) == 3.05 and round((us_real.loc[2026] / us_real.max() - 1) * 100) == -45
    fl, ca = cd.to_real(series("FL"), f), cd.to_real(series("CA"), f)
    assert fl.idxmax() == 1991 and round(fl.max() / 1e9, 2) == 3.72 and round(fl.loc[2026] / 1e9, 2) == 0.29
    assert round((fl.loc[2026] / fl.max() - 1) * 100) == -92
    assert ca.idxmax() == 2018 and round(ca.max() / 1e9, 2) == 3.07 and round((ca.loc[2026] / ca.max() - 1) * 100) == -14
    ca_nominal = series("CA")
    assert ca_nominal.idxmax() == 2026                                                    # highest as reported, not in constant dollars

def test_every_season_of_the_data_has_a_deflator_and_the_base_season_is_exactly_one():
    f = cd.real_factors(cd.load_cpi())
    seasons = cd.load_citrus()["year"].unique()
    assert f.reindex(seasons).notna().all() and f.loc[cd.BASE_YEAR] == 1.0
    assert f.loc[1990] > 2.0 and f.loc[2026] < 1.0                       # 1990 dollars bought more than twice as much as 2025 ones cost to match


def test_averaging_eleven_months_instead_of_twelve_moves_a_season_by_under_half_a_percent():
    """Backs the Methodology on the 2026 season, whose October 2025 CPI BLS did not publish."""
    c = cd.load_cpi()
    window = lambda y: c[(c.year * 12 + c.month - 1 >= (y - 1) * 12 + 9) & (c.year * 12 + c.month - 1 <= y * 12 + 8)].cpi.to_numpy()
    worst = max(abs(np.delete(window(y), i).mean() / window(y).mean() - 1) for y in range(1990, 2025) for i in range(12))
    assert worst < 0.004                                                 # the worst single month in any season of the data (0.35%)
    w = window(2026)                                                     # October 2025 first, blank
    assert np.isnan(w[0]) and np.isnan(w[1:]).sum() == 0
    filled = np.concatenate([[(c[(c.year == 2025) & (c.month == 9)].cpi.item() + w[1]) / 2], w[1:]])   # October = mean of September and November
    assert abs(w[1:].mean() / filled.mean() - 1) < 0.002                 # the 2026 season, against a filled-in month (0.16%)


def test_season_and_calendar_year_deflators_agree_within_one_and_a_half_percent():
    """Backs the Methodology: lining the season up with its own months or with the end year barely matters."""
    c = cd.load_cpi()
    cal = c.groupby("year").cpi.mean()
    f_season = cd.real_factors(c)
    f_cal = cal.loc[2025] / cal
    both = pd.concat([f_season, f_cal], axis=1).dropna().loc[1990:2025]
    assert ((both.iloc[:, 0] / both.iloc[:, 1]) - 1).abs().max() < 0.015
    us = cd.combined_total(cd.load_citrus(), cd.load_totals(), "value_of_production_usd").dropna()
    assert (us * f_season.reindex(us.index)).idxmax() == (us * f_cal.reindex(us.index).dropna()).idxmax() == 1990   # same highest year
