"""
Helpers for the US citrus-by-state data (data/citrus_by_state.csv, written by
src/fetch_industry_data.py): loading, totals that never hide a gap, and the
check that flags a published yield that conflicts with NASS's own production
and acreage.

Totals rule: a total (for a year, a state or a fruit) is shown only when every
series that NASS publishes in that year has a value. A series is "published in
a year" if the year falls inside the first and last year NASS published it. So a
value NASS withheld, a year with no row (Texas 1991), or a series that has not
started yet leaves a visible gap; a series that has ended (Arizona oranges after
2012) is simply no longer part of the total. Nothing is estimated or filled in.
"""

import numpy as np
import pandas as pd

FRUIT_ORDER = ["Oranges", "Grapefruit", "Tangerines", "Lemons", "Tangelos"]
STATE_NAMES = {"FL": "Florida", "CA": "California", "TX": "Texas", "AZ": "Arizona"}

# Where NASS itself printed a different number for a value flagged by yield_conflicts().
CONFLICT_CITATIONS = {
    ("Oranges", "CA", 2022): (
        "NASS's Citrus Fruits 2022 Summary (September 2022) prints 289 boxes per acre for "
        "California oranges in 2021-22 (140,000 acres, 40.4 million boxes)."
    ),
}


def load_citrus(path="data/citrus_by_state.csv"):
    return pd.read_csv(path)


def expected_grid(df, measure, state=None):
    """One row per fruit, state and year in which NASS publishes the measure.

    `value` is NaN where NASS withheld the value or published no row. `published`
    is True when a row exists. Restrict to one state with `state`.
    """
    d = df[df["measure"] == measure]
    if state is not None:
        d = d[d["state"] == state]
    parts = []
    for (fruit, st), g in d.groupby(["fruit", "state"]):
        years = range(int(g["year"].min()), int(g["year"].max()) + 1)
        grid = pd.DataFrame({"fruit": fruit, "state": st, "year": list(years)})
        parts.append(grid.merge(g[["year", "value", "status"]], on="year", how="left"))
    if not parts:
        return pd.DataFrame(columns=["fruit", "state", "year", "value", "status", "published"])
    out = pd.concat(parts, ignore_index=True)
    out["published"] = out["value"].notna() | out["year"].isin(d["year"])
    return out


def complete_grid(df, measure, state=None):
    """The expected grid with every value set to NaN in years where any component is missing."""
    grid = expected_grid(df, measure, state)
    if grid.empty:
        return grid
    incomplete = grid.groupby("year")["value"].transform(lambda s: s.isna().any())
    grid = grid.copy()
    grid.loc[incomplete, "value"] = np.nan
    return grid


def complete_total(df, measure, by=None, state=None):
    """Total of a measure per year (or per year and `by`), NaN in years with a missing component.

    `by` is "fruit" or "state" to get one column per group.
    """
    grid = complete_grid(df, measure, state)
    if grid.empty:
        return pd.Series(dtype=float)
    keys = ["year"] if by is None else ["year", by]
    total = grid.groupby(keys)["value"].sum(min_count=1)
    return total if by is None else total.unstack(by)


def incomplete_years(df, measure, state=None):
    """Years in which the total for the measure has a missing component."""
    grid = expected_grid(df, measure, state)
    return sorted(grid.loc[grid["value"].isna(), "year"].unique().tolist()) if not grid.empty else []


def yield_conflicts(df, tolerance=0.15):
    """Published yields that differ from utilized boxes / bearing acres by more than `tolerance`.

    That ratio is NASS's own definition of yield, and in every other year of the
    data the two agree. Returns fruit, state, year, published, implied, gap.
    """
    w = df.pivot_table(index=["fruit", "state", "year"], columns="measure", values="value")
    need = ["yield_boxes_per_acre", "production_boxes", "bearing_acres"]
    if not set(need) <= set(w.columns):
        return pd.DataFrame(columns=["fruit", "state", "year", "published", "implied", "gap"])
    w = w.dropna(subset=need)
    w["implied"] = w["production_boxes"] / w["bearing_acres"]
    w["gap"] = w["yield_boxes_per_acre"] / w["implied"] - 1
    bad = w[w["gap"].abs() > tolerance].reset_index()
    return bad.rename(columns={"yield_boxes_per_acre": "published"})[["fruit", "state", "year", "published", "implied", "gap"]]


def blank_conflicts(df):
    """Copy of the data with flagged yield values set to NaN (the file itself is never changed)."""
    out = df.copy()
    for _, r in yield_conflicts(df).iterrows():
        mask = ((out["fruit"] == r["fruit"]) & (out["state"] == r["state"]) & (out["year"] == r["year"])
                & (out["measure"] == "yield_boxes_per_acre"))
        out.loc[mask, "value"] = np.nan
    return out


def year_ranges(years):
    """[2009, 2010, 2011, 2013] -> "2009-2011, 2013"."""
    years = sorted(set(int(y) for y in years))
    parts, start = [], None
    for i, y in enumerate(years):
        if start is None:
            start = prev = y
        elif y == prev + 1:
            prev = y
        else:
            parts.append((start, prev)); start = prev = y
        if i == len(years) - 1:
            parts.append((start, prev))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in parts)


def pct_change(new, old):
    return (new / old - 1) * 100
