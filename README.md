# Florida Citrus Yield Forecasting

![Florida Citrus Yield Forecasting dashboard](docs/screenshot.png)

An end-to-end pipeline and interactive dashboard that pulls real USDA NASS yield data and NOAA weather observations, engineers agronomic weather features, benchmarks an ARIMA baseline against LightGBM, and compares four large Florida orange-producing counties.

**Live dashboard:** <https://florida-citrus-yield-forecast.onrender.com/> (free tier - the first load after idle can take about 40 seconds)

> **Scope note.** USDA NASS does not publish county-level citrus *yield* or *production* (checked for oranges and citrus totals, in both the survey and Census of Agriculture programs; production is published at state level only). The forecasting models therefore target **Florida statewide orange yield**. County-level analysis (Polk, Hendry, DeSoto, Highlands - four large orange-producing counties; see [Missing and withheld data](#missing-and-withheld-data)) is limited to what is actually published or measurable: Census bearing acreage and local weather. **No county yield is estimated or fabricated anywhere in this project.**

## Headline findings

- **Florida orange yield fell 87% from its 2004 peak (38,520 lb/acre) to its 2023 low (5,130 lb/acre).** 2024 recovered slightly to 7,020.
- **Bearing orange acreage fell 37% to 47% in every county, measured across each county's published Census totals:** Polk -46.5% (102,295 to 54,692 acres, 2002-2022), DeSoto -37.3% (67,394 to 42,234, 2002-2022), Hendry -44.7% (94,267 to 52,114, 2012-2022), Highlands -46.3% (75,984 to 40,799, 2002-2017). The periods differ because USDA withheld some totals (see [Missing and withheld data](#missing-and-withheld-data)).
- **Both models failed to anticipate the 2023-24 collapse, and neither beats a naive baseline.** On a two-year holdout, ARIMA scored RMSE 5,860 and LightGBM 10,457 lb/acre - both over-predicted heavily - while simply repeating the previous year's yield scored 4,834. Over 17 one-step-ahead rolling folds (2008-2024), the naive baseline (4,222) was about even with ARIMA (4,290) and better than LightGBM (6,782) (see [Model results](#model-results)). The collapse sits below anything in the 1990-2022 training window (minimum 11,250 in 2018), which tree models cannot extrapolate to.
- **Frost days ranked 7th of 12 in the fitted model** (by split count); lagged yield, temperature, GDD, and the trend term all ranked above it. Because the weather inputs are approximate (see [Known limitations](#known-limitations)), this is weak evidence about frost, not a finding that frost doesn't matter.
- **Frost exposure differs by county in this data.** Highlands averages 2.5 bloom-season frost days per year over the 25 years with complete winter records (max 14), versus 0.8 for Polk (all 35 years). Part of that gap reflects which stations each county has and how many are averaged, so read it as approximate rather than a clean geographic comparison. 2010 is the worst frost year in all four counties (tied with 1996 and 2001 in DeSoto), consistent with the January 2010 Florida freeze.

## Data

| Dataset | Source | Details |
|---|---|---|
| Statewide orange yield | USDA NASS QuickStats (`api_GET`) | `ORANGES`, `YIELD`, `BOXES / ACRE`, all classes, state level, 1990-2024 (35 rows). Converted to lb/acre at 90 lb/box, the standard Florida orange box weight. |
| Daily weather (central Florida) | NOAA CDO v2 `/data`, GHCND | TMAX, TMIN, PRCP from Lakeland Linder, Tampa International, Orlando Executive, and Sebring (Sebring only from Dec 2007). 106,289 daily records. |
| County bearing acreage | USDA Census of Agriculture | Oranges, all varieties combined, 2002/2007/2012/2017/2022, four counties: 20 county-years, of which 16 are published totals and 4 are withheld by USDA and left blank. Published every five years; never interpolated. |
| County daily weather | NOAA CDO v2 `/data`, GHCND | Two or more verified stations per county, 1990-2024. 281,383 daily records. |

Notes on data handling:

- NOAA station IDs were verified by querying actual observations across decades, not by trusting the station catalog (for example, Bartow Municipal is registered but returns no records).
- A physically-motivated outlier filter rejects sensor errors (TMAX outside 20-110 F, TMIN outside -5-85 F, PRCP outside 0-20 in). It removed 12 of 281,395 county records (e.g. a 115 F daily high, 101 F daily lows) and none of the state-level records.
- Weather features for the statewide model come from the four central-Florida stations above, averaged per day. This is a proxy for statewide conditions, not a statewide measurement.
- **Snapshot date.** The committed data was fetched on 2026-09-16. Upstream data can change: re-running the county fetch on 2026-10-14 returned 81 additional NOAA records (27 days of February 2018 at Lakeland Linder) that were not yet published at the first fetch, with no existing value changed. They do not affect any feature, and the committed snapshot was kept so the statewide and county files stay consistent.

## Missing and withheld data

The project reports what USDA and NOAA actually publish and shows gaps where they don't. Nothing is estimated, averaged, or interpolated to fill a gap: a filled-in value would be a modeled number sitting beside measured ones, and for withheld values there is nothing to check it against.

| Case | What it means here |
|---|---|
| **Not published** | County-level citrus yield, production, and sales have no records at all in the NASS data checked (oranges and citrus totals, survey and Census programs). The models therefore target statewide yield. |
| **Withheld by USDA** | The Census marks four county-year acreage totals "(D)", withheld to avoid disclosing individual operations' data: Hendry 2002 and 2007, DeSoto 2012, Highlands 2022. They are blank in the data (`status = withheld`) and appear as gaps in the dashboard chart. In each case USDA still published one orange variety (e.g. Highlands 2022: Valencia, 27,449 acres) but not the all-varieties total; those partial figures are not county totals and are not used. |
| **Gaps on our side** | Days missing from a weather station's record (see [Known limitations](#known-limitations)). |

**Why these four counties.** Polk, Hendry, DeSoto, and Highlands were chosen from the project's initial list of seven counties as large orange producers. Among counties with published 2022 totals, Polk (54,692 acres), Hendry (52,114), and DeSoto (42,234) rank first to third, and Hardee (37,623, not on the initial list) ranks fourth. Highlands' 2022 total is withheld, so its rank that year cannot be determined; it is kept for its large published totals through 2017 and because it has the highest bloom-season frost exposure of the four.

## Pipeline

```bash
git clone https://github.com/brianravelo28/florida-citrus-yield-forecast.git
cd florida-citrus-yield-forecast
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requires Python 3.11 or newer. `requirements.txt` is pinned to the versions the live deployment runs on (Python 3.14); the pins do not install on Python 3.9.

The cleaned datasets and model outputs are committed, so you can launch the dashboard immediately:

```bash
python run_dashboard.py          # http://127.0.0.1:8050  (run from the repo root)
```

To rebuild everything from the source APIs, get free keys from [USDA NASS QuickStats](https://quickstats.nass.usda.gov/api) and [NOAA CDO](https://www.ncei.noaa.gov/cdo-web/token) and export them as environment variables (the scripts read them at run time and stop with a clear message if they are unset; no key is stored in the code):

```bash
export NASS_KEY=your-nass-key           # Windows PowerShell: $env:NASS_KEY = "your-nass-key"
export NOAA_TOKEN=your-noaa-token

# Statewide yield model (a failed API call stops the run and writes nothing)
python src/fetch_data.py                 # NASS yield + NOAA weather (a few minutes)
python src/feature_engineering.py        # merge + 13 feature columns -> data/df_model.csv
python src/train_models.py               # ARIMA, LightGBM, baselines, rolling origin -> results/
python src/stress_indicator.py           # -> results/stress_indicator.csv

# County comparison panel (same fail-loud behavior)
python src/fetch_county_data.py          # acreage + county weather (roughly 10-15 minutes)
python src/county_feature_engineering.py # -> data/county_features.csv
```

## Features

`df_model.csv` has 35 rows (one per year) and 16 columns: `county_name`, `year`, `yield_lbs_acre`, and the 13 feature columns below (12 model inputs plus the `log_yield` target). Temperatures are in degrees F and precipitation in mm. Daily values are averaged across stations before aggregation.

**Missing weather is missing, never zero.** A feature is calculated only when every calendar day of its window (Jan-Mar or May-Aug) has an observation; otherwise it is left blank (NA). The statewide series is complete for every year, so none of its features are NA. In the county panel 36 of 140 county-years are missing at least one of the frost, temperature, or GDD features the dashboard shows, and they appear as gaps or as "*missing*" in the charts.

| Feature | Definition |
|---|---|
| `frost_days_bloom` | Days with TMIN <= 32 F, Jan-Mar |
| `tmax_mean_grow`, `tmin_mean_grow` | Mean daily max / min temperature, May-Aug |
| `temp_variance_grow` | **Standard deviation** (not variance) of daily max temperature, May-Aug. The name comes from the original project brief; it is kept so file and column names stay stable |
| `gdd_total_grow` | Growing degree days, base 50 F, May-Aug |
| `precip_total_grow` | Total precipitation, May-Aug |
| `precip_rolling_30/60/90` | Largest 30/60/90-calendar-day rolling precipitation sum within May-Aug |
| `precip_deviation` | `precip_total_grow` minus its mean over the series: wetter or drier than normal. It is the same information as `precip_total_grow` shifted by a constant, so it is redundant in the models (importance 0); it is used for the stress score, which takes its absolute value so droughts and floods both count |
| `yield_lag1` | Previous year's yield |
| `year_numeric` | Calendar year (trend) |
| `log_yield` | `log(1 + yield_lbs_acre)`, the LightGBM target |

## Model results

Two models are compared against a **naive baseline: "yield stays at last year's value"**. ARIMA(1,1,1) uses yield only. LightGBM uses 12 standardized inputs and a `log_yield` target (1991 onward, after dropping the first lag row), with `learning_rate=0.05`, `num_leaves=31`, `max_depth=5`, `min_data_in_leaf=10`, 200 rounds.

### 2023-24 holdout (train 1990-2022)

| Method | RMSE (lb/acre) | MAE (lb/acre) | 2023 pred. | 2024 pred. |
|---|---|---|---|---|
| Actual | - | - | 5,130 | 7,020 |
| Naive, one step (previous year's actual yield) | 4,834 | 4,230 | 11,700 | 5,130 |
| Naive, multi step (2022 repeated) | 5,704 | 5,625 | 11,700 | 11,700 |
| ARIMA(1,1,1), yield only | 5,860 | 5,775 | 11,902 | 11,798 |
| LightGBM, weather + lag + trend | 10,457 | 10,419 | 16,439 | 16,548 |

The methods do not all get the same information: ARIMA and the multi-step baseline forecast both years from the end of 2022, while LightGBM and the one-step baseline use each year's actual previous-year yield. Only two test points, so this is a diagnosis of the 2023-24 break, not a ranking.

### Rolling origin, 2008-2024 (17 one-step-ahead folds)

For each year from 2008 on, every method is fit on earlier years only and predicts that one year using the previous year's actual yield, so all three are on equal footing (`src/train_models.py`, per-fold results in `results/rolling_origin_folds.csv`).

| Method | RMSE, all folds | MAE, all folds | RMSE, last 5 years |
|---|---|---|---|
| Naive (previous year's yield) | 4,222 | 3,531 | 3,580 |
| ARIMA(1,1,1) | 4,290 | 3,575 | 3,767 |
| LightGBM | 6,782 | 5,678 | 7,385 |

**Neither model beats repeating last year's yield.** ARIMA is about even with it, and LightGBM is clearly worse: it over-predicted in every year from 2010 on, lagging a steadily falling series. In this data, weather plus lagged yield adds no predictive value beyond last year's yield. That fits the 2023-24 collapse, whose weather looks ordinary. Caveats: 17 overlapping folds is a small sample; ARIMA failed to converge cleanly in 1 of the 17 fits; and ARIMA's rolling numbers differ by about 1 lb/acre across statsmodels versions.

Feature importance (LightGBM split counts from the 2023-24 holdout model - not SHAP):

| Rank | Feature | Splits |
|---|---|---|
| 1 | `yield_lag1` | 57 |
| 2 | `tmax_mean_grow` | 44 |
| 3 | `tmin_mean_grow` | 42 |
| 3 | `year_numeric` | 42 |
| 5 | `gdd_total_grow` | 36 |
| 6 | `precip_total_grow` | 21 |
| 7 | `frost_days_bloom` | 19 |

No forecast beyond 2024 is produced.

## Climate stress indicator

A weather-based score per year, with thresholds computed from 1990-2020:

```
stress = 0.4 * min(frost_days / p75_frost_days, 2)
       + 0.3 * min(|precip_deviation| / std_precip_deviation, 2)
       + 0.2 * clip(mean_gdd / gdd, 0.5, 2)
       + 0.1 * 1[yield < 25th percentile of yield]
```

`HIGH` > 1.0, `MODERATE` > 0.5, otherwise `LOW`. Result across 35 years: 8 HIGH (1996, 1997, 1999, 2001, 2009, 2010, 2015, 2018), 14 MODERATE, 13 LOW.

The indicator is built from weather inputs (plus a low-yield flag), so it does not register disease or hurricane damage: it scores 2023 - the record-low yield year - as LOW (0.36). Treat it as a frost/precipitation/heat risk gauge, not a yield-loss predictor.

## Dashboard

Four-tab Plotly Dash app (`src/app.py`), with zoom/legend interaction hints under every chart.

1. **Overview** - KPI cards computed from the data (latest yield, 5-year average, peak yield, latest stress level), historical yield with the ARIMA and LightGBM holdout predictions for 2023-24, and the stress-score timeline.
2. **Weather Analysis** - temperature, precipitation, and bloom-season frost-day time series; top-10 LightGBM feature importance.
3. **Scenarios** - slider for a 0-50% increase in frost days relative to the 1990-2024 average (0.77 days/year). Illustrative only: it assumes 2,000 lb/acre lost per additional frost day (an assumption, not a fitted coefficient), $0.45/lb, and a county-sized 50,000 acres at the statewide average yield (see [Known limitations](#known-limitations)). At +50%, yield goes from 7,020 to 6,249 lb/acre, about $17.4M in lost revenue.
4. **County Comparison** - county checklist; bloom-season frost days by county (years with incomplete winter records appear as breaks in the line, not zeros); Census bearing-acreage trends (withheld totals shown as gaps, with a footnote naming them); and a **Yearly Outlook** panel (year dropdown, opening on 2018, the latest year with complete data for every county) comparing frost days, mean max temperature, and GDD across the selected counties, with incomplete values labeled "*missing*".

## Known limitations

- **Yield is statewide; weather is central Florida.** The statewide yield model uses four central-Florida stations as a proxy.
- **Small evaluation samples.** The headline holdout rests on two test points. The 17-fold rolling-origin evaluation is more informative but still small, with overlapping training sets. There is no hyperparameter tuning and no prediction intervals.
- **The 2023-24 collapse is unexplained by the features.** Citrus greening (HLB) and hurricane damage are not modelled.
- **Scenario dollars are a stylized example, not a county estimate.** USDA publishes no county-level yield, so the only yield available is the statewide average (7,020 lb/acre in 2024). To make the dollar impact tangible, the scenario applies that average to a fixed 50,000 acres - about the size of the two largest orange counties with published Census totals (Polk 54,692 and Hendry 52,114 bearing acres in 2022) - and asks what a county-sized grove area would lose if it yielded at the state average and frost days rose. This rests on an assumption that cannot be tested here: that a county yields roughly the state average. The 50,000-acre figure is a fixed input in the code rather than computed from the data, and the 2,000 lb/acre-per-frost-day loss and $0.45/lb price are assumptions too. Acreage only scales the dollar total (the per-acre change does not depend on it), so read the dollar figure as a sense of scale, not a forecast.
- **Some county acreage totals are withheld by USDA** (4 of 20), so county acreage trends cover different periods. See [Missing and withheld data](#missing-and-withheld-data).
- **Some county weather is missing.** Incomplete weather windows are left blank, not counted as zero (see [Features](#features)). In the county panel, 36 of 140 county-years are missing at least one of the frost, temperature, or GDD values the dashboard shows, and 19 are missing rainfall (worst: Highlands 2022, with 9 of 123 May-Aug days observed). The statewide series is complete.
- **Station coverage varies, and the weather is approximate.** The set of stations behind the statewide series changes over time (for example Tampa alone in 1996-98), county stations have different start and end dates, and averaging stations before counting frost days dilutes frost. See [docs/METHODOLOGY.md](docs/METHODOLOGY.md) for the timeline.
- **Weather windows are offset from the crop year.** NASS labels a Florida citrus season by its end year, but the calendar-year weather windows are matched to that label without adjustment, so they are offset by roughly a year from the crop's actual bloom and growth. The effect on results was not measured.

## Project structure

```
src/
  fetch_data.py                  # NASS yield + NOAA weather (statewide model)
  feature_engineering.py         # weather aggregation, 13 feature columns
  train_models.py                # ARIMA + LightGBM
  stress_indicator.py            # climate stress score
  fetch_county_data.py           # county acreage + county weather
  county_feature_engineering.py  # per-county features
  app.py                         # Dash dashboard (4 tabs)
data/                            # nass_yield, noaa_weather, df_model, county_acreage, county_weather, county_features (CSV)
results/                         # model_results.json, stress_indicator.csv
docs/                            # schema, methodology, API notes, citations
run_dashboard.py                 # local entry point
render.yaml                      # Render settings (reference)
RENDER_DEPLOYMENT.md             # deployment notes
```

## Deployment

Deployed on [Render](https://render.com) (build: `pip install -r requirements.txt`; start: `gunicorn src.app:server --bind 0.0.0.0:$PORT`). The data and results files are committed because the app loads them at startup, and no API keys are needed at runtime. See [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md).

## License

MIT - see [LICENSE](LICENSE).

Data: USDA NASS QuickStats, USDA Census of Agriculture, NOAA NCEI Global Historical Climatology Network (daily).
