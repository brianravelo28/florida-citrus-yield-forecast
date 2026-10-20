# Methodology

What the code does and why. Headline results live in the [README](../README.md); the numbers here are the supporting detail.

Terms: **NASS** (USDA National Agricultural Statistics Service); **NOAA** (National Oceanic and Atmospheric Administration); **GHCND** (Global Historical Climatology Network daily, NOAA's station dataset); **TMAX / TMIN / PRCP** (daily maximum and minimum temperature, and precipitation); **GDD** (growing degree days: heat accumulated above 50 F); **ARIMA** (autoregressive integrated moving average, a time-series model) and **ADF** (augmented Dickey-Fuller, a test for non-stationarity); **RMSE / MAE** (root mean squared and mean absolute error); **HLB** (huanglongbing, citrus greening disease).

## Scope

- **Target:** Florida statewide orange yield (lb/acre), 1990-2024, annual. NASS publishes citrus yield and production only at state level, so county yield cannot be modelled (see [API_SOURCES.md](API_SOURCES.md)).
- **Predictors:** weather from two fixed NOAA stations (Tampa International and the Archbold Biological Station), plus lagged yield and a year trend. Because NASS publishes yield only statewide, the weather is matched to a statewide number; since Florida oranges are grown mostly in the central and southern citrus belt, stations in that region are the relevant proxy and north Florida's different climate matters little. Checked against the 2022 Census of Agriculture (state total 321,722 bearing orange acres, fetched 2026-10-20): Polk 54,692, Hendry 52,114, DeSoto 42,234 and Hardee 37,623 acres are 58% of it; the 27 counties with published totals are 81.8%; eight north-of-Orlando and Panhandle counties with published totals (Alachua, Lafayette, Taylor, Wakulla, Santa Rosa, Marion, Volusia, Citrus) hold 1,276 acres, 0.4%. Twelve counties' totals are withheld, together 58,571 acres, of which Highlands alone is at least 27,449 (the Valencia total USDA published), so the four withheld northern counties (Escambia, Walton, Suwannee, Putnam) hold at most about 31,000 acres (under 10%) and probably far less. In the 2017 Census, Polk, Hendry, DeSoto, Highlands and Hardee were 55.5% of 397,764 acres. The weather is a stable regional proxy, not a measurement of statewide conditions or of the groves themselves (see [Weather stations](#weather-stations)). Using the four county stations instead would leave 9 to 12 of 35 years blank for each of Polk, Hendry and DeSoto, too few to train on.
- **County panel:** descriptive only. One NOAA station per county plus Census bearing acreage; no county yield is estimated.

## Data preparation

1. **Yield:** `BOXES / ACRE` x 90 lb/box (`src/fetch_data.py`). The fetcher requires all 35 years to be present.
2. **Weather:** daily TMAX/TMIN/PRCP per station from NOAA CDO v2. Readings outside plausible Florida bounds (TMAX 20-110 F, TMIN -5-85 F, PRCP 0-20 in) are dropped as sensor errors. This removed 7 of 140,193 county records (Lakeland 2: 2, Arcadia: 4, Moore Haven Lock 1: 1) and none of the 76,689 statewide records.
3. **Season labels.** NASS labels a Florida citrus season by its end year (the 2022-23 season, which includes Hurricane Ian, is `year = 2023`). The calendar-year weather windows are matched to that label without adjustment, so they are offset by roughly a year from the crop's actual bloom and growth. The effect on results was not measured.
4. **Snapshot dates.** `nass_yield.csv` and `county_acreage.csv` were fetched on 2026-09-16. The weather files (`noaa_weather.csv`, `county_weather.csv`) and the station coverage probe were fetched on 2026-10-20, when the station set changed. NOAA can backfill published data: between two fetches a month apart it added 27 days of February 2018 at Lakeland Linder without altering any existing value. Treat a fetch as a snapshot of that date.

## Weather stations

### Why two fixed stations

Averaging whichever stations report each day lets the series change meaning as stations start and stop. With four stations (Lakeland Linder, Tampa, Orlando Executive, Sebring) the set behind the average changes by year: Lakeland and Tampa in 1990-95, **Tampa alone in 1996-98**, Orlando and Tampa in 1999-2007, Sebring added in 2008, Lakeland back in 2012. That makes trends partly an artifact of which stations reported. Sebring is a colder station, so adding it in 2008 raised the apparent frost level. Averaging stations before counting frost also dilutes real frosts: a freeze at one station but not the others is smoothed away.

To fix the station set, `src/station_coverage.py` requested actual observations (the NOAA catalog's date ranges are not evidence of data) for 20 candidate stations in Polk, Highlands, Hendry and DeSoto counties and the stations already in use, for every year of 1990-2024. The full per-station-year counts are in `data/station_coverage_matrix.csv` (raw counts by month in `data/station_coverage.csv`). Years with a complete window, out of 35 (bloom window: every night of Jan-Mar TMIN observed; growing window: at least 95% of May-Aug days observed for TMAX, TMIN and PRCP):

| Station (county) | Bloom | Growing | Both | First-last year with data |
|---|---|---|---|---|
| **Archbold Biological Station** (Highlands) | 35 | 35 | **35** | 1990-2024 |
| **Tampa International** (Hillsborough) | 35 | 35 | **35** | 1990-2024 |
| Lakeland 2 (Polk) | 27 | 28 | 26 | 1996-2024 |
| Moore Haven Lock 1 (Glades) | 28 | 31 | 26 | 1990-2024 |
| Orlando Executive (Orange) | 24 | 26 | 24 | 1998-2024 |
| Mountain Lake (Polk) | 27 | 28 | 21 | 1990-2024 |
| Arcadia (DeSoto) | 24 | 26 | 21 | 1990-2021 |
| Big Cypress (Hendry) | 18 | 17 | 15 | 2002-2024 |
| Devils Garden (Hendry) | 16 | 22 | 14 | 1990-2018 |
| Lakeland Linder (Polk) | 14 | 18 | 13 | 1990-2024 |
| Avon Park 2 W (Highlands) | 13 | 18 | 10 | 1990-2022 |
| Bartow 1 SE (Polk) | 13 | 19 | 7 | 1990-2024 |
| Sebring (Highlands) | 4 | 16 | 4 | 2008-2024 |

Counties come from NOAA's station metadata. Only Archbold and Tampa report essentially every year, so they are the fixed statewide set. Requiring every day of every station in a larger set to be observed would leave 18 of 35 years NA with Mountain Lake added, and 27 with Lakeland 2 as well, too few rows to train on.

**What the pair is and is not.** Tampa is on the Gulf coast (Hillsborough County) and Archbold is in south Highlands County; neither is in the Polk grove area. The series is a stable regional proxy, and levels such as frost-day counts are not comparable with the earlier four-station series. **Archbold is a notably cold site** (open scrub, 6.2 frost days a year in 1990-2007) and Tampa is mild (0.6), so the pair's frost level sits between them and is dominated by Archbold. Compare trends over time in this series, not absolute levels against other sources.

### Sensitivity to the station choice

Rebuilt with `src/station_sensitivity.py` from the committed weather (same feature code, stress score computed on the rebuilt series):

| Station set | Mean frost days, 1990-2007 | Mean frost days, 2008-2024 | Min-temperature trend (growing season, F/decade) | HIGH stress years |
|---|---|---|---|---|
| Four stations, whichever reported (`65e8eee`) | 0.61 | 0.94 | 0.21 | 1996, 1997, 1999, 2001, 2009, 2010, 2015, 2018 |
| **Tampa + Archbold (used)** | **1.94** | **1.82** | **0.96** | 1996, 2001, 2002, 2007, 2010, 2012 |
| Tampa only | 0.56 | 0.53 | 1.10 | 1996, 2001, 2010 |
| Archbold only | 6.17 | 6.59 | 0.82 | 1996, 2000, 2001, 2002, 2010, 2013, 2018 |

- **The 2008 rise in frost days was an artifact.** With the station set fixed it disappears: frost is flat (Tampa + Archbold 1.94 to 1.82; Tampa only 0.56 to 0.53; Archbold only 6.17 to 6.59). Earlier, the rise from 0.61 to 0.94 coincided with Sebring joining.
- **The minimum-temperature trend depends on the stations,** 0.21 F per decade in the earlier mixed series against 0.82-1.10 in every fixed set. This is a statement about the data series, not a climate finding.
- **The stress-indicator ranking is station-dependent.** Only 1996, 2001 and 2010 are HIGH in all three fixed-station versions; the other years change with the stations. The stress score is an unvalidated heuristic and should be read that way.
- Model errors for the other station sets were not computed; the table covers the features and the stress score. For the pair used, errors are in the README.

### Comparison with the four-station series

The left column below is the committed result at commit `65e8eee`, the last commit before the station change; it is a fixed record, and no file in the current tree reproduces it.

| | Four stations mixed (`65e8eee`) | Tampa + Archbold (current) |
|---|---|---|
| ARIMA holdout RMSE (2023-24) | 5,860 | 5,860 (yield only, unchanged) |
| LightGBM holdout RMSE | 10,457 | 10,521 |
| Rolling one-step RMSE: naive / ARIMA / LightGBM | 4,222 / 4,290 / 6,782 | 4,222 / 4,289 / 7,278 |
| LightGBM top features (split count) | `yield_lag1` 57, `tmax_mean_grow` 44, `tmin_mean_grow` 42; frost 7th (19) | `precip_total_grow` 56, `year_numeric` 54, `frost_days_bloom` 32; frost 3rd |

The model conclusion is unchanged: neither model beats repeating last year's yield. The feature ranking reshuffled completely when the weather inputs changed, so it is only a rough guide (31 training rows, split counts rather than gain or SHAP).

## Missing weather

**Missing weather is missing, never zero.** Filling missing rainfall with 0 mm, or counting days with no record as "no frost", would understate frost counts and sums and stretch "30-day" windows across missing days. The rules are:

- **Fixed station set.** A day counts as observed only if every station in the input reported the variable that day; otherwise it is missing. Nothing is filled from other stations.
- **Frost days (Jan-Mar):** every night of the window must be observed, because a missing night may have been a frost. Otherwise `frost_days_bloom` is blank.
- **Growing-season features (May-Aug):** computed from the observed days if at least 95% of the window's 123 days are observed (up to 6 missing); otherwise blank. Means and the standard deviation describe the observed days. Sums (`precip_total_grow`, `gdd_total_grow`) cover the observed days and are **not scaled up**, so they can be up to about 5% low in a year with gaps. Rolling rainfall maxima only use windows of consecutive observed days. The 95% cutoff is a practical choice, not a statistical standard. Across the county stations, relaxing it to 90% would recover only 1 more year in each of Polk, Hendry and DeSoto; requiring 100% would add 3 NA years to Polk, 12 to Hendry and 8 to DeSoto.
- **Data-quality columns:** `bloom_days_missing` and `grow_days_missing` record how many days of each window had no observation (for growing season, the most-missing of TMAX, TMIN and PRCP), so a reader can see how complete any year is.

Statewide, one year is affected: Tampa lacks 2 days of its 2019 growing season (TMAX Aug 1; TMIN Jun 26-27), so 2019's growing-season features use 121 of 123 days. The statewide series has no NA features. In the county panel, counts of blank values out of 140 county-years: `frost_days_bloom` 26; `tmax_mean_grow`, `tmin_mean_grow`, `temp_variance_grow`, `gdd_total_grow`, `precip_total_grow` and `precip_deviation` 18; `precip_rolling_90` 27. 30 county-years are missing at least one of the frost, TMAX or GDD values the dashboard shows.

## Features

Every feature is calculated from the fixed-station daily series above; temperatures are degrees F and precipitation is mm.

| Feature | Definition |
|---|---|
| `frost_days_bloom` | Days with TMIN <= 32 F, Jan-Mar |
| `tmax_mean_grow`, `tmin_mean_grow` | Mean daily max / min temperature, May-Aug |
| `temp_variance_grow` | **Standard deviation** (not variance) of daily max temperature, May-Aug. The name is kept so file and column names stay stable |
| `gdd_total_grow` | Growing degree days, base 50 F: the sum of max(0, (TMAX + TMIN)/2 - 50), May-Aug |
| `precip_total_grow` | Total precipitation, May-Aug |
| `precip_rolling_30/60/90` | Largest 30/60/90-calendar-day rolling precipitation sum within May-Aug |
| `precip_deviation` | `precip_total_grow` minus its mean over the series: wetter or drier than normal. It is the same information as `precip_total_grow` shifted by a constant, so it is redundant in the models (importance 0); it is used in the stress score, which takes its absolute value so droughts and floods both count |
| `yield_lag1` | Previous year's yield |
| `year_numeric` | Calendar year (trend) |
| `log_yield` | `log(1 + yield_lbs_acre)`, the LightGBM target |

That is 12 model inputs plus the target. Exact columns are in [SCHEMA.md](SCHEMA.md).

## Models and evaluation

- **ARIMA(1,1,1)** on yield alone, fit on 1990-2022. An ADF test on the training series gives p = 0.988 (non-stationary), consistent with differencing.
- **LightGBM** regression on `log_yield` using 12 standardized inputs, trained on 1991-2022 (the first year is dropped for its missing lag; rows with NA features are dropped): `learning_rate=0.05`, `num_leaves=31`, `max_depth=5`, `min_data_in_leaf=10`, 200 rounds. Predictions are back-transformed with `expm1`.
- **Naive baseline:** "yield stays at last year's value". Reported two ways on the 2023-24 holdout (one step: previous year's actual yield; multi step: 2022 repeated for both years) so it can be compared with each model on the same information.
- **Evaluation 1, holdout:** train through 2022, test on 2023 and 2024. Two test points, and the methods do not all get the same information (ARIMA forecasts both years from 2022; LightGBM uses each year's actual lag), so error estimates are very noisy and not like-for-like.
- **Evaluation 2, rolling origin** (`rolling_origin_evaluation` in `src/train_models.py`): for each test year from 2008 to 2024, fit every method on earlier years only and predict that one year, using the previous year's actual yield. 17 folds, equal information for all methods. LightGBM folds train on 17-33 rows. ARIMA is refit each fold (no convergence warnings in the current run; its rolling numbers differed by about 1 lb/acre between statsmodels versions in an earlier check). A test year whose weather features are NA would be skipped for every method; none are at present. Per-fold results are in `results/rolling_origin_folds.csv`.
- **Feature importance** is LightGBM's split count (`feature_importance()` default) on the holdout model, not SHAP or gain. It is a rough guide only: with 31 training rows, ties and small changes in the inputs reorder the ranks.
- **Why LightGBM underperforms:** tree ensembles predict averages of training targets and cannot go below the lowest values seen in training (11,250 lb/acre, in 2018), while 2023-24 actuals were 5,130 and 7,020. The rolling folds show the same pattern across time: LightGBM over-predicted in 15 of 17 years (every year from 2010 on), lagging a falling series. Loosening `min_data_in_leaf` did not fix it in a one-off re-fit, so it is not simply a small-leaf constraint.

## Climate stress indicator

`src/stress_indicator.py` computes, with reference statistics from 1990-2020:

```
stress = 0.4 * min(frost_days / p75_frost_days, 2)
       + 0.3 * min(|precip_deviation| / std_precip_deviation, 2)
       + 0.2 * clip(mean_gdd / gdd, 0.5, 2)
       + 0.1 * 1[yield < 25th percentile of yield]
```

`HIGH` > 1.0, `MODERATE` > 0.5, otherwise `LOW`. Result across 35 years: 6 HIGH (1996, 2001, 2002, 2007, 2010, 2012), 16 MODERATE, 13 LOW.

- **Frost-term cliff.** The 75th percentile of frost days is 2.5, so the frost term reaches its cap at 5 days: every year with 5 or more frost days scores the same on frost (2010's 12 days scores no higher than 1996's 5).
- The yield flag uses the same year's yield, so the score is not a pure weather measure.
- It is built from weather inputs, so it does not register disease or hurricane damage: 2023, the record-low yield year, scores MODERATE (0.66) and 2024 LOW (0.50).
- **Unvalidated.** The score's Spearman correlation with yield is +0.32: higher "stress" goes with higher yield, the wrong direction for a stress measure (the cause was not investigated). Treat it as a descriptive frost/rain/heat gauge, not a yield-loss predictor.

## County panel

`src/fetch_county_data.py` and `src/county_feature_engineering.py` repeat the weather aggregation per county using one primary station each, with the same fixed-station and missing-data rules. A single station per county keeps each county's series the same instrument every year; each series describes that station, not the whole county, and gaps stay blank.

| County | Station | NOAA county (metadata) | Notes |
|---|---|---|---|
| Polk | Lakeland 2 | Polk | Starts late 1995, so 1990-94 are blank; 2010 and 2014 frost blank |
| Hendry | Moore Haven Lock 1 | **Glades** | Hendry's own stations are blank in 20+ of 35 years (Devils Garden: 21; Big Cypress: 20), so the nearest usable station is used, in neighboring Glades County about 20 km from Devils Garden. It is labeled this way on the dashboard. NOAA's metadata lists it under Glades County, not Hendry |
| DeSoto | Arcadia | DeSoto | Only in-county station; records end April 2021, so 2022-24 are blank |
| Highlands | Archbold Biological Station | Highlands | Complete, but a cold site (6.4 frost days a year on average, up to 25 in 2010) |

Frost days per bloom season, 1990-2024: Highlands (Archbold) 6.4 average, max 25; DeSoto 3.8, max 14; Polk 1.7, max 5; Hendry 1.0, max 6. Differences between counties mix real geography with where each station sits, so read them as differences between stations. 2010 is the worst frost year in DeSoto, Hendry and Highlands; Polk's 2010 winter record is incomplete (Lakeland 2 is missing nights), so its worst recorded winters are four years tied at 5 days (1996, 2001, 2003, 2009).

Precipitation deviation is relative to each county's own mean. Bearing acreage comes from the Census of Agriculture (every five years) and is left empty in other years.

**Withheld acreage.** Four of the 20 county-year totals are withheld by USDA (marked `(D)`): Hendry 2002 and 2007, DeSoto 2012, Highlands 2022. They are kept as blank rows with `status = withheld`, plotted as gaps, and named in the chart footnote, which is generated from the data. They are not estimated: a modeled value would sit beside measured ones, and since USDA withheld exactly these numbers there is nothing to validate an estimate against. Filling them would also be inconsistent: three of the four gaps fall at the start or end of a county's series (Hendry 2002 and 2007, Highlands 2022), which would require extrapolation rather than interpolation. For those four rows USDA published a single orange variety instead (Hendry 2002 and 2007 and Highlands 2022: Valencia only; DeSoto 2012: Mid & Navel only; e.g. Highlands 2022: Valencia, 27,449 acres); that is not a county total, so it is not used. Trend statements therefore use only each county's published totals (Polk 2002-2022, DeSoto 2002-2022, Hendry 2012-2022, Highlands 2002-2017).

**County selection.** The four counties are large orange producers. Among counties with published 2022 totals, Polk (54,692 acres), Hendry (52,114) and DeSoto (42,234) rank first to third and Hardee (37,623) ranks fourth but is not included. Highlands' 2022 total is withheld, so its rank that year is unknown; it is kept for its large published totals through 2017.

## Scenario tab

Illustrative, not estimated from data: the slider scales the 1990-2024 average frost days (1.89 per year in the current series), each added frost day is assumed to cost 2,000 lb/acre, and dollars use $0.45/lb on 50,000 acres. At +50%, the 2024 yield of 7,020 lb/acre falls to about 5,134 and the revenue loss is about $42.4M. The framing is "what would a county-sized grove area lose if it yielded at the statewide average?": county yield is unpublished, so the statewide average stands in for it, and 50,000 acres approximates the largest counties with published totals (Polk 54,692, Hendry 52,114 bearing acres in 2022). The assumption that a county yields about the state average cannot be tested. The 2,000 lb/acre figure is an assumption, not a fitted coefficient, and the acreage is a fixed input that only scales the dollar total, so the dollar figure is a sense of scale, not a forecast. The scenario's yield floor is 5,000 lb/acre.

## Reproducibility

API keys are read from the `NASS_KEY` and `NOAA_API_KEY` (or `NOAA_TOKEN`) environment variables; nothing is stored in the code. Both fetchers retry transient failures, then stop and write nothing if any request fails, any Census acreage query returns other than exactly one row, or a county station has data in fewer than 20 years; there is no substitute-data fallback. Years in which a station has no observations are reported and left blank.

What has and has not been verified:
- With the four-station weather (commit `65e8eee`), the pipeline was re-run end to end and reproduced the committed files, on Python 3.9 / pandas 2.0 and on Python 3.14 / pandas 3.0.
- **The current station set was fetched, engineered and trained once, on Python 3.14 / pandas 3.0, on 2026-10-20.** Cross-version reproducibility of these new outputs has not been re-checked.
- `requirements.txt` is pinned to the live deployment's versions and was installed and run in a clean Python 3.14 environment.
- The feature code is covered by tests (`tests/`, run in CI).
