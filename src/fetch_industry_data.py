"""
Fetch US citrus data by fruit and state from USDA NASS QuickStats (survey data,
state level, 1990-2026): bearing acres, yield, price received and value of
production, for oranges, grapefruit, tangerines, lemons and tangelos.

Output: data/citrus_by_state.csv, one row per fruit, state, year and measure.
A value NASS withheld or did not publish is left blank with a note; nothing is
estimated or filled in, and no value is ever changed. After fetching, the script
prints a sanity report (gaps, blanks, and yields or prices far from their own
series' median) so odd values can be checked against NASS's own publications
before they are charted.

Needs NASS_KEY; a failed request stops the run and writes nothing.
"""

import sys
import time

import pandas as pd

from fetch_data import END_YEAR, PRELIMINARY_YEARS, START_YEAR, FetchError, get_json, require_key

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
                raw = str(r["Value"]).strip()
                note = SUPPRESSED.get(raw, "")
                try:
                    value = float(raw.replace(",", "")) if not note else float("nan")
                except ValueError:
                    raise FetchError(f"{fruit} {measure} {r['state_alpha']} {r['year']}: unexpected value {raw!r}")
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
    return out


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
    except FetchError as e:
        print(f"\n[FAILED] {e}\nNothing was written; existing data files are unchanged.")
        sys.exit(1)
    df.to_csv("data/citrus_by_state.csv", index=False)
    print(f"\n[OK] Saved data/citrus_by_state.csv ({len(df)} rows)")
    sanity_report(df)
    consistency_check(df)


if __name__ == "__main__":
    main()
