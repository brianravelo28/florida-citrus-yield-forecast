"""
Fetch US citrus data by fruit and state from USDA NASS QuickStats (survey data,
state level, 1990-2026): bearing acres, yield, price received and value of
production, for oranges, grapefruit, tangerines, lemons and tangelos.

Output: data/citrus_by_state.csv, one row per fruit, state, year and measure,
and data/citrus_totals_by_state.csv, NASS's own state totals across all citrus
(QuickStats commodity CITRUS TOTALS: bearing acres and value of production,
2008 on). A value NASS withheld or did not publish is left blank with a note;
nothing is estimated or filled in, and no value is ever changed. After
fetching, the script prints a sanity report (gaps, blanks, and yields or prices
far from their own series' median) and a comparison of the fruit values with
NASS's totals, so odd values can be checked against NASS's own publications
before they are charted.

Needs NASS_KEY; a failed request stops the run and writes nothing.
"""

import os
import sys
import time

import pandas as pd
import requests


START_YEAR, END_YEAR = 1990, 2026

# NASS labels a citrus season by its END year: 2023 is the 2022-23 season. NASS publishes the
# season that ends in END_YEAR as a preliminary estimate in August and revises it a year later,
# so only that last year is marked "preliminary".
PRELIMINARY_YEARS = {END_YEAR}


class FetchError(RuntimeError):
    """A data fetch failed. Nothing should be written when this is raised."""


def require_key(name):
    """Read an API credential from the environment; fail clearly if it is unset.

    The key is read at fetch time, not import time, and the error never echoes a value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise FetchError(f"{name} is not set. Get a free key (see README) and export it as an environment variable.")
    return value


def get_json(url, params, headers=None, attempts=3):
    """GET and parse JSON, retrying transient failures; raise FetchError if all fail.

    Error text deliberately omits the request URL: requests' own messages
    include it, and the NASS key travels in the query string.
    """
    reason = "unknown error"
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            reason = f"HTTP {e.response.status_code}"
        except (requests.RequestException, ValueError) as e:
            reason = type(e).__name__
        if attempt < attempts:
            time.sleep(2 ** attempt)
    raise FetchError(f"{url} failed after {attempts} attempts ({reason})")

FRUITS = ["ORANGES", "GRAPEFRUIT", "TANGERINES", "LEMONS", "TANGELOS"]

# measure name -> (QuickStats statisticcat_desc, unit_desc, reference_period_desc, util_practice_desc).
# Prices are reported for the marketing year; the others for the calendar year. "PHD EQUIV" is
# packinghouse-door equivalent, the same basis as the value of production. Utilized production
# is the quantity actually used (boxes, or tons so that different fruits can be added up).
ALL_UTIL = "ALL UTILIZATION PRACTICES"
MEASURES = {
    "bearing_acres": ("AREA BEARING", "ACRES", "YEAR", ALL_UTIL),
    "yield_boxes_per_acre": ("YIELD", "BOXES / ACRE", "YEAR", ALL_UTIL),
    "production_boxes": ("PRODUCTION", "BOXES", "YEAR", "UTILIZED"),
    "production_tons": ("PRODUCTION", "TONS", "YEAR", "UTILIZED"),
    "value_of_production_usd": ("PRODUCTION", "$, PHD EQUIV", "YEAR", ALL_UTIL),
    "price_usd_per_box": ("PRICE RECEIVED", "$ / BOX, PHD EQUIV", "MARKETING YEAR", ALL_UTIL),
}

SUPPRESSED = {"(D)": "withheld (D)", "(NA)": "not available (NA)", "(S)": "suppressed (S)", "(Z)": "less than half the unit (Z)", "": "blank"}


def fetch_series(fruit, stat, unit, period, util):
    """Rows for one fruit and measure, all states, one row per state and year."""
    params = {
        "key": require_key("NASS_KEY"), "commodity_desc": fruit, "agg_level_desc": "STATE",
        "source_desc": "SURVEY", "statisticcat_desc": stat, "unit_desc": unit,
        "year__GE": str(START_YEAR), "year__LE": str(END_YEAR), "format": "json",
    }
    rows = get_json("https://quickstats.nass.usda.gov/api/api_GET/", params).get("data", [])
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Totals only: all classes, the stated utilization, no domain split.
    df = df[(df["class_desc"] == "ALL CLASSES") & (df["util_practice_desc"] == util)
            & (df["domain_desc"] == "TOTAL")]
    df = df[df["reference_period_desc"] == period]
    return df


def parse_value(raw, label):
    """One QuickStats Value string -> (number or NaN, note). A suppression code keeps its reason."""
    raw = str(raw).strip()
    note = SUPPRESSED.get(raw, "")
    try:
        return (float(raw.replace(",", "")) if not note else float("nan")), note
    except ValueError:
        raise FetchError(f"{label}: unexpected value {raw!r}")


def build_table():
    records = []
    for fruit in FRUITS:
        for measure, (stat, unit, period, util) in MEASURES.items():
            df = fetch_series(fruit, stat, unit, period, util)
            if df.empty:
                print(f"  [--] {fruit} {measure}: no rows")
                continue
            if df.duplicated(["state_alpha", "year"]).any():
                raise FetchError(f"{fruit} {measure}: more than one total row for a state-year")
            for _, r in df.iterrows():
                value, note = parse_value(r["Value"], f"{fruit} {measure} {r['state_alpha']} {r['year']}")
                year = int(r["year"])
                records.append({
                    "fruit": fruit.title(), "state": r["state_alpha"], "year": year, "measure": measure,
                    "value": value, "note": note,
                    "status": "preliminary" if year in PRELIMINARY_YEARS else "reported",
                })
            print(f"  [OK] {fruit.title()} {measure}: {df['state_alpha'].nunique()} states, {len(df)} rows")
            time.sleep(0.2)
    out = pd.DataFrame(records).sort_values(["fruit", "state", "measure", "year"]).reset_index(drop=True)
    if out.empty:
        raise FetchError("NASS returned no citrus rows")
    # QuickStats can return NASS's forecast for the coming season even when the request stops at
    # END_YEAR (observed: year 2027 production, issued October 2026). A forecast is not data, so
    # anything after END_YEAR is dropped, and the drop is reported.
    after = out[out["year"] > END_YEAR]
    if len(after):
        print(f"  [NOTE] dropped {len(after)} rows after {END_YEAR} (NASS forecasts for the coming season): "
              f"years {sorted(after['year'].unique())}, measures {sorted(after['measure'].unique())}")
    return out[out["year"] <= END_YEAR].reset_index(drop=True)


TOTALS_COMMODITY = "CITRUS TOTALS"
TOTALS_MEASURES = ("bearing_acres", "value_of_production_usd")
TOTALS_FILE = "data/citrus_totals_by_state.csv"


def build_totals():
    """NASS's own state totals across all citrus (acres and value), one row per state, year and measure.

    QuickStats publishes them for 2008 on. Same filters and the same handling of withheld values and
    forecast rows as the fruit table. Raises FetchError rather than return a partial table.
    """
    records = []
    for measure in TOTALS_MEASURES:
        stat, unit, period, util = MEASURES[measure]
        df = fetch_series(TOTALS_COMMODITY, stat, unit, period, util)
        if df.empty:
            raise FetchError(f"{TOTALS_COMMODITY} {measure}: no rows")
        if df.duplicated(["state_alpha", "year"]).any():
            raise FetchError(f"{TOTALS_COMMODITY} {measure}: more than one total row for a state-year")
        for _, r in df.iterrows():
            value, note = parse_value(r["Value"], f"{TOTALS_COMMODITY} {measure} {r['state_alpha']} {r['year']}")
            year = int(r["year"])
            records.append({"state": r["state_alpha"], "year": year, "measure": measure, "value": value, "note": note,
                            "status": "preliminary" if year in PRELIMINARY_YEARS else "reported"})
        print(f"  [OK] {TOTALS_COMMODITY} {measure}: {df['state_alpha'].nunique()} states, {len(df)} rows")
        time.sleep(0.2)
    out = pd.DataFrame(records).sort_values(["measure", "state", "year"]).reset_index(drop=True)
    return out[out["year"] <= END_YEAR].reset_index(drop=True)


def totals_check(fruit_df, totals, tolerance=0.01):
    """Compare the sum of the fruit values with NASS's own state total, state-year by state-year.

    Prints how many agree exactly, which differ because a fruit value is blank (the sum is then
    partial), and which differ although every fruit value is present. Changes nothing.
    """
    print("\n" + "=" * 60 + "\nFRUIT SUMS vs NASS STATE TOTALS\n" + "=" * 60)
    for measure in TOTALS_MEASURES:
        parts = fruit_df[(fruit_df["measure"] == measure)]
        sums = parts.groupby(["state", "year"])["value"].agg(total="sum", blanks=lambda s: int(s.isna().sum())).reset_index()
        m = totals[totals["measure"] == measure].merge(sums, on=["state", "year"], how="left")
        m["diff"] = m["total"] - m["value"]
        exact = (m["diff"].abs() < 1).sum()
        partial = m[(m["diff"].abs() >= 1) & (m["blanks"] > 0)]
        off = m[(m["diff"].abs() >= 1) & (m["blanks"] == 0)]
        print(f"\n{measure}: {len(m)} state-years in NASS's totals; sum equals the total in {exact}; "
              f"differs with a blank fruit value (partial sum) in {len(partial)}; differs with every fruit value present in {len(off)}")
        if len(off):
            off = off.assign(pct=(off["diff"] / off["value"] * 100).round(2))
            print(off[["state", "year", "value", "total", "diff", "pct"]].to_string(index=False))
            if (off["pct"].abs() > tolerance * 100).any():
                print(f"  [CHECK] a difference above {tolerance:.0%}")


def sanity_report(df, ratio=3.0):
    """Print gaps, blanks and values far from their own series' median. Changes nothing."""
    print("\n" + "=" * 60 + "\nSANITY REPORT\n" + "=" * 60)
    blanks = df[df["value"].isna()]
    print(f"\nBlank values: {len(blanks)} of {len(df)}")
    if len(blanks):
        g = blanks.groupby(["fruit", "state", "measure"])["year"].apply(lambda s: ", ".join(map(str, sorted(s))))
        print(g.to_string())
    print("\nSeries with years missing inside their own range (no row at all):")
    found = False
    for (fruit, state, measure), s in df.groupby(["fruit", "state", "measure"]):
        have = set(s["year"]); gap = sorted(set(range(min(have), max(have) + 1)) - have)
        if gap:
            found = True; print(f"  {fruit} {state} {measure}: {gap}")
    if not found:
        print("  none")
    print(f"\nYields and prices more than {ratio:g}x above or below their own series' median (check against NASS):")
    flagged = False
    for (fruit, state, measure), s in df[df["measure"].isin(["yield_boxes_per_acre", "price_usd_per_box"])].groupby(["fruit", "state", "measure"]):
        s = s.dropna(subset=["value"])
        if len(s) < 8:
            continue
        med = s["value"].median()
        for _, r in s[(s["value"] > med * ratio) | (s["value"] < med / ratio)].iterrows():
            flagged = True
            print(f"  {fruit} {state} {measure} {int(r['year'])}: {r['value']:g} (series median {med:g})")
    if not flagged:
        print("  none")


def consistency_check(df, tolerance=0.15):
    """Compare each published yield with utilized boxes / bearing acres (NASS's own definition).

    In years that agree the two match closely (California oranges 2021: 49.0M boxes /
    138,000 acres = 355 = the published yield). A published yield more than `tolerance`
    away from that ratio is flagged for checking; nothing is changed.
    """
    w = df.pivot_table(index=["fruit", "state", "year"], columns="measure", values="value")
    need = {"yield_boxes_per_acre", "production_boxes", "bearing_acres"}
    if not need <= set(w.columns):
        print("\nConsistency check skipped: a needed measure is missing")
        return pd.DataFrame()
    w = w.dropna(subset=list(need))
    w["implied_yield"] = w["production_boxes"] / w["bearing_acres"]
    w["gap"] = (w["yield_boxes_per_acre"] / w["implied_yield"]) - 1
    bad = w[w["gap"].abs() > tolerance].reset_index()
    print(f"\nYield vs utilized boxes / bearing acres: {len(w)} fruit-state-years compared, "
          f"{len(bad)} differ by more than {tolerance:.0%}")
    if len(bad):
        print(bad[["fruit", "state", "year", "yield_boxes_per_acre", "implied_yield", "gap"]]
              .round({"implied_yield": 0, "gap": 2}).to_string(index=False))
    return bad


def main():
    print("=" * 60 + "\nCITRUS BY STATE (USDA NASS, survey, 1990-%d)\n" % END_YEAR + "=" * 60)
    try:
        df = build_table()
        totals = build_totals()
    except FetchError as e:
        print(f"\n[FAILED] {e}\nNothing was written; existing data files are unchanged.")
        sys.exit(1)
    df.to_csv("data/citrus_by_state.csv", index=False)
    totals.to_csv(TOTALS_FILE, index=False)
    print(f"\n[OK] Saved data/citrus_by_state.csv ({len(df)} rows) and {TOTALS_FILE} ({len(totals)} rows)")
    sanity_report(df)
    consistency_check(df)
    totals_check(df, totals)


if __name__ == "__main__":
    main()
