# Methodology

What the code does and why. Headline results are in the [README](../README.md); the numbers here are the supporting detail.

Terms: **NASS** (USDA National Agricultural Statistics Service); **QuickStats** (NASS's online database and API); **PHD equivalent** (packinghouse-door equivalent: a price or value measured at the packinghouse door, so fruit sold fresh and fruit processed are on one basis); **HLB** (huanglongbing, citrus greening disease).

## Scope

The project describes the US citrus industry by fruit and state (bearing acreage, yield, utilized production, price and value of production, 1990-2026) from NASS state surveys. It builds no model and makes no forecast.

## Citrus data (NASS)

`src/fetch_industry_data.py` pulls state-level survey data from QuickStats (`agg_level_desc=STATE`, `source_desc=SURVEY`) for oranges, grapefruit, tangerines, lemons and tangelos, for Florida, California, Texas and Arizona, and writes `data/citrus_by_state.csv` (one row per fruit, state, year and measure). All files were pulled on 2026-11-03 and are real observations; none is synthetic. NASS revises its newest season a year later, so treat each pull as a snapshot of its date.

| Measure | QuickStats statistic and unit | Notes |
|---|---|---|
| Bearing acres | `AREA BEARING`, `ACRES` | |
| Yield | `YIELD`, `BOXES / ACRE` | Florida oranges also carry a gallons-per-box series; only boxes per acre is used |
| Utilized production | `PRODUCTION`, `BOXES` and `TONS`, utilization `UTILIZED` | Boxes cover 1990-2026; tons exist only for recent years, so tons are fetched but not used for totals |
| Value of production | `PRODUCTION`, `$, PHD EQUIV` | Packinghouse-door equivalent dollars, nominal |
| Price per box | `PRICE RECEIVED`, `$ / BOX, PHD EQUIV`, marketing year | |

Only the all-classes total is used (not single varieties or fresh/processing splits), and the script stops if a state-year has more than one row.

- **Seasons.** NASS labels a season by its end year (2023 is the 2022-23 season). The season ending in 2026 is NASS's preliminary estimate (published August 2026) and is marked `status = preliminary`; all earlier seasons are `reported`.
- **Forecast rows are dropped.** QuickStats can return NASS's forecast for the coming season even when the request stops at 2026 (it returned 22 production rows for the season ending in 2027, issued October 2026). A forecast is not data, so anything after the last season is dropped, the drop is printed, and a test checks the file.
- **Blanks stay blank.** A value NASS withheld ("(D)") or marked not available is kept as a blank row with the reason in the `note` column. Of 2,483 values, 63 are blank (48 withheld, 15 not available), mostly California and Arizona value and price figures for tangerines and lemons in 2009-2016 and Arizona oranges in 2010-2012. Texas has no 1991 row at all for oranges or grapefruit.

## Totals and gaps

A total (for a year, a state or a fruit) is shown only when every series NASS publishes in that year has a value. A series counts as published in a year if the year falls between its first and last published year (`src/citrus_data.py`). So a withheld value, a missing year (Texas 1991) or a series that has not started leaves a visible gap, while a series that has ended (Arizona oranges after 2012) simply stops being part of the total. Stacked charts leave a whole year empty instead of drawing a partial stack. Consequences: the acreage total has a gap in 2010-2012, and the value totals in 1991 and 2009-2016. A published sum for 2012 is already $3.42 billion with four values missing, so the true 2012 total could exceed 2017's $3.53 billion; **the dashboard therefore states no peak for the US value total.** Acreage peaks and per-state figures use each total's own complete years.

## Checks on the data

- **Yield against production and acreage.** NASS defines yield as utilized boxes divided by bearing acres, and in the data the two agree. The fetch compares every published yield with that ratio (463 fruit-state-years) and flags any that differ by more than 15%. **One does: California oranges in 2022.** QuickStats publishes 58 boxes per acre, but the same database gives 39.1 million utilized boxes and 137,000 bearing acres for 2022, which imply about 285 (the 2022 crop fell about 20% from 2021 in a drought year, but not to 58). NASS's printed [Citrus Fruits 2022 Summary](https://esmis.nal.usda.gov/sites/default/release-files/j9602060k/pn89ff24k/1544cx74m/cfrt0922.txt) (September 2022, table "Orange Acreage, Yield, Utilization, Price, and Value by Type") gives California all oranges for 2021-22 as 140,000 acres, 289 boxes per acre and 40,400 thousand boxes, with later revisions to the production and acreage figures. The published 58 is therefore at odds with the printed report and with two other values in QuickStats. It stays in the data file; the dashboard draws it as a gap with a footnote, and does not substitute a computed value. How the error entered QuickStats is not known.
- **Other unusual values.** The fetch also prints yields and prices more than three times away from their own series' median. The ones examined (Florida after 2023, Texas 1992) agree with NASS's production and acreage: Florida's collapse and the Texas freeze-year lows are real, not data errors.

## Nominal dollars, shares and units

- **Dollars are nominal.** Value of production and price are not adjusted for inflation, so dollar values are not compared across decades as if they bought the same amount. Each state's **share** of the US value in the same year is unaffected by inflation, so the headline uses shares and physical measures (acres, boxes) for change over time. An inflation adjustment would need a price index from another source and is not applied.
- **Yield units differ by state.** Box weights differ across states, so raw boxes per acre are not comparable across states. The dashboard offers yield as a share of each state's own peak, and notes this on the yield chart.
- **Dollars add up, boxes do not.** Different fruits and states have different box weights, so totals across them use acres and dollars only.

## Reproducibility

The NASS key is read from the `NASS_KEY` environment variable; nothing is stored in the code. The fetch retries transient failures, then stops and writes nothing if any request fails or a state-year has more than one citrus row.

What was run: the fetch ran end to end on Python 3.14 / pandas 3.x on 2026-11-03, and the committed data file is its output. Tests (`tests/`, run in CI on Python 3.13 and 3.14) cover the totals rule, the yield cross-check and the committed data; they do not cover the API fetch or the dashboard. `requirements.txt` is pinned and was installed in a clean Python 3.14 environment.
