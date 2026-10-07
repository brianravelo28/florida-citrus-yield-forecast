# Methodology

What the code does and why. Results live in the [README](../README.md) so they have one source of truth.

## Scope

- **Target:** Florida statewide orange yield (lb/acre), 1990-2024, annual. NASS publishes citrus yield and production only at state level, so county yield cannot be modelled (see `docs/API_SOURCES.md`).
- **Predictors:** weather from four central-Florida stations, plus lagged yield and a year trend. Weather is a regional proxy for statewide conditions.
- **County panel:** descriptive only. Per-county weather features and Census bearing acreage; no county yield is estimated.

## Data preparation

1. **Yield:** `BOXES / ACRE` x 90 lb/box (`src/fetch_data.py`). The fetcher requires all 35 years to be present.
2. **Weather:** daily TMAX/TMIN/PRCP per station. Readings outside plausible Florida bounds (TMAX 20-110 F, TMIN -5-85 F, PRCP 0-20 in) are dropped as sensor errors; this removed 12 of 281,395 county records and none of the statewide records. The fetcher requires every year to have some weather data.
3. **Station averaging:** `feature_engineering.py` averages stations per day before aggregating. A frost at one station but not the others is therefore diluted in `frost_days_bloom`.
4. **Missing precipitation:** a day with temperatures but no `PRCP` value is treated as 0 mm (`fillna(0)`). The statewide series has full May-Aug precipitation coverage in every year. The county panel does not: 19 of 140 county-years have fewer than 123 observed May-Aug precipitation days, and three are badly affected (Highlands 2022: 9 days; DeSoto 1993: 29; DeSoto 1990: 34). Treat precipitation features for those county-years as unreliable.
5. **Rolling windows** are computed over available observation days, not calendar days, so station gaps stretch the window.

## Features

`frost_days_bloom` (Jan-Mar), growing-season (May-Aug) temperature mean/variance, growing degree days (base 50 F), precipitation total and rolling maxima, precipitation deviation from the 1990-2024 mean, lagged yield, and year. Definitions are in the README; exact columns in `docs/SCHEMA.md`.

## Models and evaluation

- **ARIMA(1,1,1)** on yield alone, fit on 1990-2022. An ADF test on the training series gives p = 0.988 (non-stationary), consistent with differencing.
- **LightGBM** regression on `log_yield` using 12 standardized inputs, trained on 1991-2022 (the first year is dropped for its missing lag): `learning_rate=0.05`, `num_leaves=31`, `max_depth=5`, `min_data_in_leaf=10`, 200 rounds. Predictions are back-transformed with `expm1`.
- **Evaluation** is a single temporal holdout: train through 2022, test on 2023 and 2024. There is no rolling-origin cross-validation; with two test points, error estimates are very noisy.
- **Feature importance** is LightGBM's split count (`feature_importance()` default), not SHAP or gain.
- **Why LightGBM underperforms here:** tree ensembles predict averages of training targets and cannot go below the lowest values seen in training (11,250 lb/acre, in 2018), while 2023-24 actuals were 5,130 and 7,020.

## Climate stress indicator

`src/stress_indicator.py` combines a frost term (days vs. the 75th percentile), a precipitation-deviation term, an inverse-GDD term, and a flag for yield below the 25th percentile, with weights 0.4/0.3/0.2/0.1. The first three terms are capped (frost and precipitation at 2; GDD clipped to 0.5-2). Reference statistics use 1990-2020. The yield flag uses the same year's yield, so it is not a pure weather measure. Because the inputs are weather-based, the score does not capture disease or hurricane damage.

## County panel

`src/fetch_county_data.py` and `src/county_feature_engineering.py` repeat the weather aggregation per county using each county's own stations (`docs/API_SOURCES.md`). Precipitation deviation is relative to each county's own mean. Bearing acreage comes from the Census of Agriculture (every five years) and is left empty in other years.

**Withheld acreage.** Four of the 20 county-year totals are withheld by USDA (marked `(D)`): Hendry 2002 and 2007, DeSoto 2012, Highlands 2022. They are kept as blank rows with `status = withheld`, plotted as gaps, and named in the chart footnote, which is generated from the data. They are not estimated: a modeled value would sit beside measured ones, and since USDA withheld exactly these numbers there is nothing to validate an estimate against. Filling them would also be inconsistent: three of the four gaps fall at the start or end of a county's series (Hendry 2002 and 2007, Highlands 2022), which would require extrapolation rather than interpolation. For those four rows USDA published a single orange variety instead (e.g. Highlands 2022: Valencia, 27,449 acres); that is not a county total, so it is not used. Trend statements therefore use only each county's published totals (Polk 2002-2022, DeSoto 2002-2022, Hendry 2012-2022, Highlands 2002-2017).

**County selection.** The four counties were chosen from the project's initial seven-county list. Among counties with published 2022 totals, Polk, Hendry, and DeSoto rank first to third and Hardee (37,623 acres, not on the initial list) ranks fourth; Highlands' 2022 total is withheld, so its rank that year is unknown.

## Scenario tab

Illustrative, not estimated from data: the slider scales the 1990-2024 average frost days (0.77/yr), each added frost day is assumed to cost 2,000 lb/acre, and dollars use $0.45/lb on 50,000 acres. The framing is "what would a county-sized grove area lose if it yielded at the statewide average?": county yield is unpublished, so the statewide average stands in for it, and 50,000 acres approximates the largest counties with published totals (Polk 54,692, Hendry 52,114 bearing acres in 2022). The assumption that a county yields about the state average cannot be tested. The 2,000 lb/acre figure is an assumption, not a fitted coefficient, and the acreage is a fixed input that only scales the dollar total.

## Reproducibility

`python src/fetch_data.py` regenerates `nass_yield.csv` and `noaa_weather.csv` from the live APIs; a fresh run reproduced the committed files exactly. Failed requests stop the run and write nothing.
