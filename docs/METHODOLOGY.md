# Methodology

What the code does and why. Results live in the [README](../README.md) so they have one source of truth.

## Scope

- **Target:** Florida statewide orange yield (lb/acre), 1990-2024, annual. NASS publishes citrus yield and production only at state level, so county yield cannot be modelled (see `docs/API_SOURCES.md`).
- **Predictors:** weather from four central-Florida stations, plus lagged yield and a year trend. Weather is a regional proxy for statewide conditions.
- **County panel:** descriptive only. Per-county weather features and Census bearing acreage; no county yield is estimated.

## Data preparation

1. **Yield:** `BOXES / ACRE` x 90 lb/box (`src/fetch_data.py`). The fetcher requires all 35 years to be present.
2. **Weather:** daily TMAX/TMIN/PRCP per station. Readings outside plausible Florida bounds (TMAX 20-110 F, TMIN -5-85 F, PRCP 0-20 in) are dropped as sensor errors; this removed 12 of 281,395 county records and none of the statewide records. The fetcher requires every year to have some weather data.
3. **Station averaging:** `feature_engineering.py` averages stations per day before aggregating. A frost at one station but not the others is therefore diluted in `frost_days_bloom`. For 2011-2019 the individual stations averaged 1.78 (Sebring), 1.12 (Lakeland), 0.33 (Orlando) and 0.22 (Tampa) Jan-Mar frost days per year, against 0.44 for the averaged series.

   **The set of stations also changes by year.** NOAA has no records for Lakeland Linder in 1996-2010 or Orlando Executive before 1998 (confirmed by querying the API directly), so the statewide weather comes from:

   | Years | Stations reporting Jan-Mar TMIN |
   |---|---|
   | 1990-1995 | Lakeland, Tampa |
   | 1996-1998 | Tampa only |
   | 1999-2007 | Orlando, Tampa |
   | 2008-2011 | Orlando, Sebring, Tampa |
   | 2012-2024 | Lakeland, Orlando, Sebring, Tampa |

   County series have the same issue: 41 of 140 county-years have only one station reporting Jan-Mar TMIN, and the average number of stations per county shifts between the 1990s and 2020s (Polk 1.7 to 4.0, Hendry 2.0 to 1.0, Highlands 1.0 to 1.6). Weather features, and frost counts in particular, are therefore approximate and not strictly comparable across years or counties. This is accepted for the project's scope; a station-consistent or gridded-weather study would be a separate analysis.

   **Season labels.** NASS labels a Florida citrus season by its end year (the 2022-23 season, which includes Hurricane Ian, is `year = 2023`). The calendar-year weather windows are matched to that label without adjustment, so they are offset by roughly a year from the crop's actual bloom and growth. The effect on results was not measured.
4. **Missing weather is missing, never zero.** A feature is calculated only when every calendar day of its window (Jan-Mar, or May-Aug) has an observation; a day counts as observed if at least one station reported that variable. Otherwise the feature is left blank (NA). This covers frost days, the temperature means and standard deviation, GDD, rainfall totals, and the rolling rain windows (which run over real calendar days). An earlier version filled missing rainfall with 0 mm and counted days with no record as "no frost", which understated frost counts and sums and stretched "30-day" windows across missing days. The statewide series has complete windows in every year, so none of its features are NA (re-running the corrected code reproduced the statewide features exactly). In the county panel 19 of 140 county-years are missing rainfall, 28 are missing TMAX/GDD, 26 TMIN, and 19 frost days; 36 are missing at least one of the frost, temperature, or GDD values the dashboard shows. The worst cases for rainfall are Highlands 2022 (9 of 123 May-Aug days observed), DeSoto 1993 (29), and DeSoto 1990 (34). `precip_deviation` uses the mean of the years that have complete rainfall.

## Features

`frost_days_bloom` (Jan-Mar), growing-season (May-Aug) temperature mean and standard deviation (the column is named `temp_variance_grow` but holds a standard deviation), growing degree days (base 50 F), precipitation total and rolling maxima, precipitation deviation from the series mean (a constant shift of the total, redundant for the models and used by the stress score), lagged yield, and year. Definitions are in the README; exact columns in `docs/SCHEMA.md`.

## Models and evaluation

- **ARIMA(1,1,1)** on yield alone, fit on 1990-2022. An ADF test on the training series gives p = 0.988 (non-stationary), consistent with differencing.
- **LightGBM** regression on `log_yield` using 12 standardized inputs, trained on 1991-2022 (the first year is dropped for its missing lag): `learning_rate=0.05`, `num_leaves=31`, `max_depth=5`, `min_data_in_leaf=10`, 200 rounds. Predictions are back-transformed with `expm1`.
- **Naive baseline:** "yield stays at last year's value". Reported two ways on the 2023-24 holdout (one step: previous year's actual yield; multi step: 2022 repeated for both years) so it can be compared with each model on the same information.
- **Evaluation 1, holdout:** train through 2022, test on 2023 and 2024. Two test points, and the methods do not all get the same information (ARIMA forecasts both years from 2022; LightGBM uses each year's actual lag), so error estimates are very noisy and not like-for-like.
- **Evaluation 2, rolling origin** (`rolling_origin_evaluation` in `src/train_models.py`): for each test year from 2008 to 2024, fit every method on earlier years only and predict that one year, using the previous year's actual yield. 17 folds, equal information for all methods. LightGBM folds train on 17-32 rows. ARIMA is refit each fold (one fold failed to converge cleanly, and ARIMA's rolling numbers differ by about 1 lb/acre between statsmodels versions). Results are in the README and per fold in `results/rolling_origin_folds.csv`.
- **Feature importance** is LightGBM's split count (`feature_importance()` default) on the holdout model, not SHAP or gain.
- **Why LightGBM underperforms:** tree ensembles predict averages of training targets and cannot go below the lowest values seen in training (11,250 lb/acre, in 2018), while 2023-24 actuals were 5,130 and 7,020. The rolling folds show the same pattern across time: LightGBM over-predicted in every year from 2010 on, lagging a falling series. Loosening `min_data_in_leaf` did not fix it in a one-off re-fit, so it is not simply a small-leaf constraint. Neither model beats the naive baseline in this data.

## Climate stress indicator

`src/stress_indicator.py` combines a frost term (days vs. the 75th percentile), a precipitation-deviation term, an inverse-GDD term, and a flag for yield below the 25th percentile, with weights 0.4/0.3/0.2/0.1. The first three terms are capped (frost and precipitation at 2; GDD clipped to 0.5-2). Reference statistics use 1990-2020. The yield flag uses the same year's yield, so it is not a pure weather measure. Because the inputs are weather-based, the score does not capture disease or hurricane damage.

## County panel

`src/fetch_county_data.py` and `src/county_feature_engineering.py` repeat the weather aggregation per county using each county's own stations (`docs/API_SOURCES.md`). Precipitation deviation is relative to each county's own mean. Bearing acreage comes from the Census of Agriculture (every five years) and is left empty in other years.

**Withheld acreage.** Four of the 20 county-year totals are withheld by USDA (marked `(D)`): Hendry 2002 and 2007, DeSoto 2012, Highlands 2022. They are kept as blank rows with `status = withheld`, plotted as gaps, and named in the chart footnote, which is generated from the data. They are not estimated: a modeled value would sit beside measured ones, and since USDA withheld exactly these numbers there is nothing to validate an estimate against. Filling them would also be inconsistent: three of the four gaps fall at the start or end of a county's series (Hendry 2002 and 2007, Highlands 2022), which would require extrapolation rather than interpolation. For those four rows USDA published a single orange variety instead (e.g. Highlands 2022: Valencia, 27,449 acres); that is not a county total, so it is not used. Trend statements therefore use only each county's published totals (Polk 2002-2022, DeSoto 2002-2022, Hendry 2012-2022, Highlands 2002-2017).

**County selection.** The four counties were chosen from the project's initial seven-county list. Among counties with published 2022 totals, Polk, Hendry, and DeSoto rank first to third and Hardee (37,623 acres, not on the initial list) ranks fourth; Highlands' 2022 total is withheld, so its rank that year is unknown.

## Scenario tab

Illustrative, not estimated from data: the slider scales the 1990-2024 average frost days (0.77/yr), each added frost day is assumed to cost 2,000 lb/acre, and dollars use $0.45/lb on 50,000 acres. The framing is "what would a county-sized grove area lose if it yielded at the statewide average?": county yield is unpublished, so the statewide average stands in for it, and 50,000 acres approximates the largest counties with published totals (Polk 54,692, Hendry 52,114 bearing acres in 2022). The assumption that a county yields about the state average cannot be tested. The 2,000 lb/acre figure is an assumption, not a fitted coefficient, and the acreage is a fixed input that only scales the dollar total.

## Reproducibility

API keys are read from the `NASS_KEY` and `NOAA_TOKEN` environment variables. Both fetchers retry transient failures, then stop and write nothing if any request fails, any Census acreage query returns other than exactly one row, or any year of weather is missing; there is no substitute-data fallback.

Verified:
- **Statewide fetch** (`python src/fetch_data.py`) reproduced the committed `nass_yield.csv` and `noaa_weather.csv` exactly.
- **County fetch** (`python src/fetch_county_data.py`, run end to end on Python 3.14) reproduced the committed `county_acreage.csv` exactly and `county_weather.csv` apart from 81 additional Lakeland Linder records (27 days of February 2018) that NOAA published after the 2026-09-16 snapshot; no existing value changed, and no feature is affected. The committed files are the 2026-09-16 snapshot.
- **Features and models** (`feature_engineering.py`, `train_models.py`) reproduce the committed `df_model.csv` and the holdout results in `model_results.json` exactly on Python 3.9 / pandas 2.0 and on Python 3.14 / pandas 3.0 (the stack the live site runs). The rolling-origin ARIMA RMSE differs by about 1 lb/acre between the two (statsmodels 0.14.6 vs 0.15.0).
- `requirements.txt` is pinned to the live deployment's versions and was installed and run in a clean Python 3.14 environment.
