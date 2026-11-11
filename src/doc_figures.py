"""
Every figure the README, the Methodology and the schema doc quote, recomputed from the committed data.

`figures()` returns the numbers; `phrases()` turns them into the exact wording the documents must
contain; `missing()` lists the ones that are absent. `python src/doc_figures.py` prints the result and
exits 1 if a document has drifted from the data; tests/test_doc_figures.py runs the same check, so a
number that changes without the text changing fails the build.

Run from anywhere; the data files are found relative to this file.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import citrus_data as cd
    import manifest
except ImportError:
    from src import citrus_data as cd
    from src import manifest

ROOT = Path(__file__).resolve().parents[1]
DOCS = {"README": "README.md", "METHODOLOGY": "docs/METHODOLOGY.md", "SCHEMA": "docs/SCHEMA.md"}


def _window(cpi, season):
    m = cpi["year"] * 12 + cpi["month"] - 1
    return cpi[(m >= (season - 1) * 12 + 9) & (m <= season * 12 + 8)]["cpi"].to_numpy()


def figures(root=ROOT):
    root = Path(root)
    df = cd.load_citrus(root / "data/citrus_by_state.csv")
    tot = cd.load_totals(root / "data/citrus_totals_by_state.csv")
    cpi = cd.load_cpi(root / "data/cpi_u_monthly.csv")
    f = {}
    last, first = int(df["year"].max()), int(df["year"].min())
    factors = cd.real_factors(cpi)
    f.update(last=last, first=first, rows=len(df), blank=int(df["value"].isna().sum()),
             withheld=int((df["note"] == "withheld (D)").sum()), not_available=int((df["note"] == "not available (NA)").sum()),
             totals_rows=len(tot), cpi_rows=len(cpi))

    # acreage: the US total and each state's share of the loss
    acres = cd.combined_total(df, tot, "bearing_acres").dropna()
    peak_year = int(acres.idxmax())
    fl_a = cd.combined_total(df, tot, "bearing_acres", state="FL")
    ca_a = cd.combined_total(df, tot, "bearing_acres", state="CA")
    lost = acres.loc[peak_year] - acres.loc[last]
    f.update(acres_peak_year=peak_year, acres_peak=acres.max(), acres_last=acres.loc[last],
             acres_fall=round((1 - acres.loc[last] / acres.max()) * 100), acres_lost=lost,
             fl_acres_peak=fl_a.loc[peak_year], fl_acres_last=fl_a.loc[last], fl_acres_lost=fl_a.loc[peak_year] - fl_a.loc[last],
             fl_acres_fall=round((1 - fl_a.loc[last] / fl_a.loc[peak_year]) * 100),
             fl_loss_share=round((fl_a.loc[peak_year] - fl_a.loc[last]) / lost * 100),
             ca_acres_peak_year=int(ca_a.idxmax()), ca_below_peak=round((1 - ca_a.loc[last] / ca_a.max()) * 100))

    # the headline's sensitivity (without Florida), the count behind the acreage chart, and the sample questions' counts
    by_state = cd.combined_total(df, tot, "bearing_acres", by="state")
    exfl = by_state.drop(columns="FL").sum(axis=1)
    value_state = cd.combined_total(df, tot, "value_of_production_usd", by="state")
    ca_stack = cd.complete_total(df, "value_of_production_usd", by="fruit", state="CA")
    ca_line = cd.combined_total(df, tot, "value_of_production_usd", state="CA")
    f.update(exfl_peak=exfl.loc[peak_year], exfl_last=exfl.loc[last], exfl_fall=round((1 - exfl.loc[last] / exfl.loc[peak_year]) * 100),
             acres_n=cd.count_values(df, "bearing_acres", years=[y for y in by_state.index if y < int(tot["year"].min())])
             + cd.count_totals(tot, "bearing_acres"),
             q1_n=cd.count_values(df, "bearing_acres", fruit="Oranges"),
             q2_n=cd.count_values(df, "value_of_production_usd", years=list(ca_stack.dropna(how="all").index), state="CA")
             + cd.count_totals(tot, "value_of_production_usd", years=list(ca_line.dropna().index), state="CA"),
             q3_n=cd.count_values(df, "value_of_production_usd",
                                  years=[y for y in value_state.dropna(how="all").index if y < int(tot["year"].min())])
             + cd.count_totals(tot, "value_of_production_usd", years=list(value_state.dropna(how="all").index)))
    pulled = {k: v["pulled"] for k, v in manifest.load(root / "data/manifest.json").items()}
    f.update(nass_pulled=pulled["data/citrus_by_state.csv"], bls_pulled=pulled["data/cpi_u_monthly.csv"])

    # value, as reported and in 2025 dollars
    value = lambda state=None: cd.combined_total(df, tot, "value_of_production_usd", state=state).dropna()
    us, fl, ca = value(), value("FL"), value("CA")
    us_r, fl_r, ca_r = (cd.to_real(s, factors) for s in (us, fl, ca))
    state_values = cd.combined_total(df, tot, "value_of_production_usd", by="state").dropna()
    share = state_values.div(state_values.sum(axis=1), axis=0) * 100
    f.update(share_fl_first=share.loc[first, "FL"], share_fl_last=share.loc[last, "FL"],
             share_ca_first=share.loc[first, "CA"], share_ca_last=share.loc[last, "CA"],
             us_peak_year=int(us.idxmax()), us_peak=us.max(), us_last=us.loc[last], us_fall=round((1 - us.loc[last] / us.max()) * 100),
             us_2014=us.loc[2014], us_2017=us.loc[2017],
             us_real_peak_year=int(us_r.idxmax()), us_real_peak=us_r.max(), us_real_last=us_r.loc[last],
             us_real_fall=round((1 - us_r.loc[last] / us_r.max()) * 100),
             fl_peak_year=int(fl.idxmax()), fl_peak=fl.max(), fl_last=fl.loc[last], fl_fall=round((1 - fl.loc[last] / fl.max()) * 100),
             fl_real_peak_year=int(fl_r.idxmax()), fl_real_peak=fl_r.max(), fl_real_last=fl_r.loc[last],
             fl_real_fall=round((1 - fl_r.loc[last] / fl_r.max()) * 100),
             ca_peak_year=int(ca.idxmax()), ca_real_peak_year=int(ca_r.idxmax()), ca_real_peak=ca_r.max(),
             ca_real_fall=round((1 - ca_r.loc[last] / ca_r.max()) * 100))

    # Florida orange yield, fruit mix
    y = df[(df.fruit == "Oranges") & (df.state == "FL") & (df.measure == "yield_boxes_per_acre")].set_index("year")["value"]
    by = lambda fruit, measure: df[(df.fruit == fruit) & (df.measure == measure)].groupby("year")["value"].sum(min_count=1)
    f.update(fl_yield_peak_year=int(y.idxmax()), fl_yield_peak=y.max(), fl_yield_low_year=int(y.idxmin()), fl_yield_low=y.min(),
             fl_yield_fall=round((1 - y.min() / y.max()) * 100), fl_yield_last=y.loc[last],
             tang_acres_first=by("Tangerines", "bearing_acres").loc[first], tang_acres_last=by("Tangerines", "bearing_acres").loc[last],
             tang_value=by("Tangerines", "value_of_production_usd").loc[last], orange_value=by("Oranges", "value_of_production_usd").loc[last],
             orange_acres_fall=round((1 - by("Oranges", "bearing_acres").loc[last] / by("Oranges", "bearing_acres").loc[first]) * 100),
             grapefruit_acres_fall=round((1 - by("Grapefruit", "bearing_acres").loc[last] / by("Grapefruit", "bearing_acres").loc[first]) * 100))

    # the yield cross-check
    w = df.pivot_table(index=["fruit", "state", "year"], columns="measure", values="value").dropna(
        subset=["yield_boxes_per_acre", "production_boxes", "bearing_acres"])
    gap = (w["yield_boxes_per_acre"] / (w["production_boxes"] / w["bearing_acres"]) - 1).abs()
    ca22, ca21 = w.loc[("Oranges", "CA", 2022)], w.loc[("Oranges", "CA", 2021)]
    f.update(yield_compared=len(w), yield_over_15=int((gap > 0.15).sum()), ca22_published=ca22["yield_boxes_per_acre"],
             ca22_implied=ca22["production_boxes"] / ca22["bearing_acres"], ca22_boxes=ca22["production_boxes"],
             ca22_acres=ca22["bearing_acres"], ca22_fall=round((1 - ca22["production_boxes"] / ca21["production_boxes"]) * 100))

    # the fruit sums against NASS's own state totals
    exact = {}
    off = []
    for measure in ("bearing_acres", "value_of_production_usd"):
        parts = df[df.measure == measure].groupby(["state", "year"])["value"].agg(total="sum", blanks=lambda s: s.isna().sum())
        m = tot[tot.measure == measure].merge(parts.reset_index(), on=["state", "year"])
        same = (m["total"] - m["value"]).abs() < 1
        exact[measure] = (len(m), int(same.sum()), int(((~same) & (m["blanks"] > 0)).sum()))
        o = m[(~same) & (m["blanks"] == 0)]
        off += [(r.state, int(r.year), (r.total / r.value - 1) * 100) for r in o.itertuples()]
    f.update(totals_state_years=exact["bearing_acres"][0], acres_exact=exact["bearing_acres"][1],
             value_exact=exact["value_of_production_usd"][1], value_partial=exact["value_of_production_usd"][2], off=sorted(off))

    # constant dollars
    cal = cpi.groupby("year")["cpi"].mean()
    both = pd.concat([factors, cal.loc[2025] / cal], axis=1).dropna().loc[1990:2025]
    diff = (both.iloc[:, 0] / both.iloc[:, 1] - 1).abs()
    worst = max(abs(np.delete(_window(cpi, s), i).mean() / _window(cpi, s).mean() - 1) for s in range(1990, 2025) for i in range(12))
    w26 = _window(cpi, last)
    filled = np.concatenate([[(cpi[(cpi.year == 2025) & (cpi.month == 9)].cpi.item() + w26[1]) / 2], w26[1:]])
    f.update(factor_1990=factors[1990], factor_2000=factors[2000], factor_2010=factors[2010], factor_last=factors[last],
             align_max=diff.max() * 100, align_mean=diff.mean() * 100, month_worst=worst * 100,
             month_2026=(np.nanmean(w26) / filled.mean() - 1) * 100)      # real values rise by this much if October is filled in
    return f


def phrases(f):
    """(document, wording) pairs: each figure as the documents state it."""
    b = lambda x: f"{x / 1e9:.2f}"           # dollars to billions
    c = lambda x: f"{x:,.0f}"
    L = f["last"]
    names = {"CA": "California", "FL": "Florida"}
    off_items = [f"{names[s]} {y} ({p:.2f}%)" for s, y, p in f["off"]]      # fruit sums above NASS's total, every fruit present
    readme = [
        f"fell {f['acres_fall']}% from its {f['acres_peak_year']} peak, from {c(f['acres_peak'])} acres to {c(f['acres_last'])} in {L} "
        f"(preliminary), and Florida accounts for {f['fl_loss_share']}% of the acres lost (n = {f['acres_n']} NASS values behind the acreage chart)",
        f"Without Florida, acreage in the other three states is {f['exfl_fall']}% lower ({c(f['exfl_peak'])} to {c(f['exfl_last'])} acres)",
        f"By Fruit tab, Oranges, Bearing acres; n = {f['q1_n']})", f"By State tab, California; n = {f['q2_n']})",
        f"Industry Overview, share chart; n = {f['q3_n']})",
        f"Pulled {f['nass_pulled']}.", f"Retrieved {f['bls_pulled']}.",
        f"Of the {c(f['acres_lost'])} bearing acres the US lost from {f['acres_peak_year']} to {L}, Florida lost {c(f['fl_acres_lost'])} ({f['fl_loss_share']}%); "
        f"California's acreage is {f['ca_below_peak']}% below its {f['ca_acres_peak_year']} peak",
        f"fell from {f['share_fl_first']:.0f}% in {f['first']} to {f['share_fl_last']:.0f}% in {L}, while California's rose from "
        f"{f['share_ca_first']:.0f}% to {f['share_ca_last']:.0f}%",
        f"was ${b(f['us_real_peak'])} billion in {f['us_real_peak_year']} (the highest year in the data) and ${b(f['us_real_last'])} billion in {L} "
        f"(preliminary), {f['us_real_fall']}% lower",
        f"the highest year is {f['us_peak_year']} (${b(f['us_peak'])} billion) and {L} is {f['us_fall']}% lower",
        f"Its bearing acres fell {f['fl_acres_fall']}% from the {f['acres_peak_year']} peak ({c(f['fl_acres_peak'])} to {c(f['fl_acres_last'])})",
        f"fell {f['fl_real_fall']}% from its {f['fl_real_peak_year']} peak in 2025 dollars (${b(f['fl_real_peak'])} billion to ${b(f['fl_real_last'])} billion)",
        f"and {f['fl_fall']}% from its {f['fl_peak_year']} peak in dollars as reported (${b(f['fl_peak'])} billion to ${b(f['fl_last'])} billion)",
        f"fell {f['fl_yield_fall']}% from its {f['fl_yield_peak_year']} peak ({f['fl_yield_peak']:.0f} boxes per acre) to its {f['fl_yield_low_year']} low "
        f"({f['fl_yield_low']:.0f}), and was {f['fl_yield_last']:.0f} in {L} (preliminary)",
        f"in 2025 dollars it is {f['ca_real_fall']}% below its {f['ca_real_peak_year']} peak (${b(f['ca_real_peak'])} billion)",
        f"Tangerine acreage grew from {c(f['tang_acres_first'])} to {c(f['tang_acres_last'])} acres ({f['first']} to {L})",
        f"tangerines were the highest-value fruit (${b(f['tang_value'])} billion, against ${b(f['orange_value'])} billion for oranges",
        f"Orange acreage is down {f['orange_acres_fall']}% from {f['first']} and grapefruit acreage {f['grapefruit_acres_fall']}%",
        f"{c(f['rows'])} rows", f"{f['totals_rows']} rows", f"{f['cpi_rows']} rows",
        f"{f['blank']} are blank (NASS withheld {f['withheld']} and marked {f['not_available']} not available)",
        f"{f['ca22_published']:.0f} boxes per acre", f"imply about {f['ca22_implied']:.0f}",
        f"the fruit sums equal NASS's acreage totals in every state-year",
    ]
    meth = [
        f"Of {c(f['rows'])} rows, {f['blank']} are blank ({f['withheld']} withheld, {f['not_available']} not available)",
        f"({f['yield_compared']} fruit-state-years)", f"{f['ca22_published']:.0f} boxes per acre",
        f"{f['ca22_boxes'] / 1e6:.1f} million utilized boxes and {c(f['ca22_acres'])} bearing acres", f"imply about {f['ca22_implied']:.0f}",
        f"fell about {f['ca22_fall']}% from 2021",
        f"equal in all {f['totals_state_years']}. For value of production they are equal in {f['value_exact']}; in {f['value_partial']} the fruit sum is partial",
        ", ".join(off_items[:-1]) + " and " + off_items[-1],
        f"by at most {max(abs(p) for _, _, p in f['off']):.2f}% where both are complete",
        f"is highest in {f['us_peak_year']} (${b(f['us_peak'])} billion), with ${b(f['us_2014'])} billion in 2014, ${b(f['us_2017'])} billion in 2017 "
        f"and ${b(f['us_last'])} billion in {L} (preliminary)",
        f"{f['factor_1990']:.2f} for 1990, {f['factor_2000']:.2f} for 2000, {f['factor_2010']:.2f} for 2010 and {f['factor_last']:.2f} for the {L} season",
        f"within {f['align_max']:.1f}% of each other in every season from 1990 to 2025 (mean difference {f['align_mean']:.2f}%)",
        f"at most {f['month_worst']:.2f}%", f"about {f['month_2026']:.2f}% higher",
        f"highest in {f['us_peak_year']} (${b(f['us_peak'])} billion) as reported and in {f['us_real_peak_year']} (${b(f['us_real_peak'])} billion, the first year of the data) in 2025 dollars; "
        f"in {L} it is {f['us_fall']}% and {f['us_real_fall']}% below those",
        f"California's value is highest in {f['ca_peak_year']} as reported and in {f['ca_real_peak_year']} (${b(f['ca_real_peak'])} billion) in 2025 dollars",
        f"Florida's is highest in {f['fl_peak_year']} as reported and in {f['fl_real_peak_year']} (${b(f['fl_real_peak'])} billion) in 2025 dollars",
    ]
    meth.append(f"Both files were pulled on {f['nass_pulled']}")
    schema = [f"pulled on {f['nass_pulled']}", f"{f['totals_rows']} rows", f"{f['cpi_rows']} rows", f"{c(f['rows'])} rows",
              f"{f['blank']} of {c(f['rows'])} ({f['withheld']} withheld, {f['not_available']} not available)"]
    return [("README", p) for p in readme] + [("METHODOLOGY", p) for p in meth] + [("SCHEMA", p) for p in schema]


def _norm(text):
    return " ".join(text.split())


def missing(root=ROOT):
    """The (document, wording) pairs that the documents do not contain."""
    root = Path(root)
    texts = {k: _norm((root / v).read_text(encoding="utf-8")) for k, v in DOCS.items()}
    return [(doc, p) for doc, p in phrases(figures(root)) if _norm(p) not in texts[doc]]


def main():
    f = figures()
    bad = missing()
    print(f"{len(phrases(f))} figures checked against {', '.join(DOCS.values())}")
    for doc, p in bad:
        print(f"  [DRIFT] {doc} does not contain: {p}")
    if bad:
        sys.exit(1)
    print("  [OK] every quoted figure matches the data")


if __name__ == "__main__":
    main()
