# Walkthrough: Florida Citrus Yield Forecasting

A study guide for the author. The goal is to re-learn this project well enough to defend it in a data analyst interview, including the parts that are weak. Written 2026-10-12 after reading every file in the repo, and updated 2026-10-14 after a round of fixes (missing-data handling, a naive baseline and rolling-origin evaluation, pinned dependencies, keys moved out of the code).

**How the numbers in this document were obtained.** Everything labeled "verified" was re-run against the committed data or the live APIs while writing this. Where something is unchecked, it says so.

**Read section 5 twice.** Reading the code end to end turned up weaknesses. The weather-data ones (5.2) are accepted approximations that are disclosed in the README and `docs/METHODOLOGY.md`. Several wrong or overclaimed statements, a missing-data bug, and the missing baseline have since been fixed (5.8). What is still open is listed at the end of 5.8.

---

## 1. The 30-second pitch (non-technical)

> Florida's orange crop has collapsed. Yield per acre is down 87% from its 2004 peak, and it's now at a fraction of what it was. I built a public dashboard that pulls real USDA crop data and NOAA weather records and asks a straightforward question: can weather explain it? In my tests, simple weather measures did not predict the 2023–24 collapse. It looks driven by things like citrus greening disease and hurricanes, which this project doesn't model. The dashboard also compares four of Florida's biggest orange-growing counties on frost exposure and acreage lost, and it's upfront about what the government doesn't publish. For example, there are no county-level yield numbers, so I show gaps instead of inventing them.

Live: <https://florida-citrus-yield-forecast.onrender.com/> (free tier; the first load after idle can take ~40 seconds).

Four numbers to have memorized (all verified):

| Number | Meaning |
|---|---|
| **-87%** | Statewide orange yield, 2004 peak (38,520 lb/acre) to 2023 low (5,130). 2024: 7,020. |
| **5,860 / 10,457** | Holdout RMSE (lb/acre) for ARIMA / LightGBM on 2023–24. Both missed badly. |
| **4,834** | Holdout RMSE of the naive baseline "predict last year's yield". It beats both models. |
| **4,222 / 4,290 / 6,782** | Rolling-origin RMSE (17 one-step folds, 2008–2024): naive / ARIMA / LightGBM. Naive is about even with ARIMA and clearly beats LightGBM. |
| **4 of 20** | County acreage totals that USDA withheld; shown as gaps, never estimated. |

The honest one-line takeaway: **the main result is negative.** Weather features plus lagged yield did not beat repeating last year's yield, and the data handling is careful. Section 5.2 explains why even the weather features can't be fully trusted.

---

## 2. How it works

### The shape of it

```
USDA NASS API ──┐
                ├─ src/fetch_data.py ──► data/nass_yield.csv  (35 rows)
NOAA CDO API ───┘                        data/noaa_weather.csv (106,289 rows)
                                                │
                                src/feature_engineering.py ──► data/df_model.csv (35 x 16)
                                                │
                     ┌──────────────────────────┴───────────────────────┐
         src/train_models.py                                src/stress_indicator.py
         ──► results/model_results.json                     ──► results/stress_indicator.csv
                     └──────────────────────────┬───────────────────────┘
                                                │
USDA Census + NOAA ─ src/fetch_county_data.py ─► data/county_acreage.csv (20 rows)
                                                 data/county_weather.csv (281,383 rows)
                     src/county_feature_engineering.py ──► data/county_features.csv (140 x 14)
                                                │
                                         src/app.py  (Dash, 4 tabs)
                          local: run_dashboard.py     live: gunicorn src.app:server on Render
```

About 2,000 lines of Python. No notebooks, no automated tests. API keys come from the `NASS_KEY` and `NOAA_TOKEN` environment variables, not the code.

### Stage by stage

**1. Fetch the statewide data: `src/fetch_data.py`**
- `fetch_nass_yield()` makes one NASS call: oranges, Florida, state level, `YIELD`, `BOXES / ACRE`, all classes, 1990–2024. Multiplies by 90 lb/box to get lb/acre. Output: 35 rows.
- `fetch_noaa_weather()` loops 4 stations x 35 years (NOAA only allows <1 year per request, 1,000 rows per page), keeps daily TMAX/TMIN/PRCP, and drops physically impossible readings via `is_plausible()` (TMAX 20–110 F, TMIN −5–85 F, PRCP 0–20 in).
- `require_key()` reads the keys from the environment at run time and stops with a clear message if unset. `get_json()` retries 3 times and raises `FetchError`. `main()` writes **nothing** unless every fetch succeeded and all 35 years are present. (This replaced an earlier version that silently substituted fake data. See section 4.)
- Verified: a fresh run reproduced both committed CSVs exactly (on 2026-10-12).

**2. Engineer features: `src/feature_engineering.py`**
- `engineer_weather_features()` is the **one shared implementation** used for both the statewide series and each county. It pivots long data to one row per date, **averaging across stations** (`aggfunc='mean'`), converts rain from inches to mm, then computes per year:
  - `frost_days_bloom`: number of days Jan–Mar with TMIN ≤ 32 F.
  - May–Aug: `tmax_mean_grow`, `tmin_mean_grow`, `temp_variance_grow` (actually a standard deviation), `gdd_total_grow` (growing degree days, base 50 F), `precip_total_grow`, and the largest 30/60/90-day rolling rain sums.
  - **Missing weather is NA, never zero:** each feature is calculated only if every calendar day of its window has an observation (the data is reindexed to the full calendar window so gaps are explicit). Rolling windows therefore run over real calendar days.
- `merge_and_finalize()` joins to yield on (county, year), adds `yield_lag1` (previous year's yield), `precip_deviation` (rain minus its mean: a "wetter/drier than normal" signal the stress score uses; it is redundant for the models), `year_numeric`, and `log_yield = log(1+yield)`. Output: 35 rows x 16 columns.
- Verified: the rewritten code reproduces the committed `df_model.csv` exactly on Python 3.9/pandas 2.0 and on Python 3.14/pandas 3.0.

**3. Train and evaluate: `src/train_models.py`**
- `fit_arima_baseline()`: ARIMA(1,1,1) on yield only, train 1990–2022; forecasts both 2023–24 test years from the end of training.
- `fit_lightgbm_holdout()`: LightGBM on 12 standardized features predicting `log_yield`; 200 rounds, learning rate 0.05, max depth 5, min 10 rows per leaf. Saves "feature importance" as split counts. (One train/test split, not cross-validation; it was previously misnamed `fit_lightgbm_wfcv`.)
- `naive_baseline()`: "yield stays at last year's value", one-step and multi-step, on the same 2023–24 holdout.
- `rolling_origin_evaluation()`: for each test year 2008–2024, fit ARIMA, LightGBM and the naive rule on earlier years only and predict that one year (17 folds, equal information for all). Writes `results/rolling_origin_folds.csv`.
- Verified: reproduces the committed holdout results exactly on both Python stacks.

**4. Stress score: `src/stress_indicator.py`**
- Score = 0.4 x frost term + 0.3 x rain-deviation term + 0.2 x inverse-GDD term + 0.1 x "yield below the 25th percentile" flag. Thresholds come from 1990–2020. HIGH > 1.0, MODERATE > 0.5, else LOW. Result: 8 HIGH, 14 MODERATE, 13 LOW.

**5. County branch: `src/fetch_county_data.py`, `src/county_feature_engineering.py`**
- Four counties (Polk, Hendry, DeSoto, Highlands). `fetch_bearing_acreage()` asks NASS for the **all-varieties** Census total per county and Census year (2002–2022). USDA marks some totals `(D)` = withheld; those become blank rows with `status = withheld`. The function raises an error unless it gets exactly one row.
- `fetch_station_weather()` / `fetch_all_county_weather()` pull each county's own stations (2–4 each; Sebring is fetched once and shared by Polk and Highlands), through the same fail-loud client and outlier filter as the statewide fetch (imported, not copied). The run requires every county to have weather in every year and writes nothing otherwise.
- `county_feature_engineering.py` runs the same shared feature function per county. Output: `county_features.csv` includes `bearing_acres` and `acreage_status` (`published`/`withheld`/blank for non-Census years), and blank weather features where a window was incomplete (36 of 140 county-years miss at least one of the frost/temperature/GDD values the dashboard shows).
- Verified: a clean end-to-end run on Python 3.14 reproduced the committed county data exactly, apart from 81 records NOAA backfilled since the original fetch (below).

**6. Dashboard: `src/app.py`**
- Loads the CSVs **once at import** (so changing data means redeploying). Four tabs: Overview (KPI cards computed from data, yield vs holdout predictions, stress timeline), Weather Analysis, Scenarios (frost slider), County Comparison (frost by county, acreage with gaps, a year dropdown "Yearly Outlook"). Missing values are shown as breaks in lines and as italic "*missing*" on bars, never as zeros; the Yearly Outlook opens on 2018, the latest year with complete data for all four counties.
- Eight charts; each has a small zoom/legend hint.

**7. Deploy: `render.yaml`, `RENDER_DEPLOYMENT.md`**
- Render runs `gunicorn src.app:server`. The CSVs/JSON the app reads are **committed to git** (they're gitignored by default, so they were force-added). No API keys are needed at runtime.

---

## 3. Key decisions

Many of these came from the **project brief** (`AGRICULTURE_QUICK_REFERENCE.md`, which is not in the repo): ARIMA(1,1,1), the LightGBM settings, the feature list, the stress weights and thresholds, the 2023–24 holdout. Be straightforward about that: *"The brief specified the approach; I implemented it, evaluated it honestly, and reported that it missed the brief's own success targets."* The brief's targets were LightGBM RMSE < 5,000 and frost days ranking #1–2 in importance. **Neither was met** (10,457; frost days ranked 7th).

**Target: statewide orange yield, not county yield.**
- *Alternatives:* county yield (what the brief wanted); production; "citrus" overall.
- *Why:* NASS publishes no county-level citrus yield or production, in either the survey or Census programs (checked). There is no `CITRUS` commodity to query either; it's `ORANGES` or `CITRUS TOTALS`.
- *Weak spot:* "orange" yield is not "citrus" yield; grapefruit and others are excluded.

**Don't fill in missing or withheld data.**
- *Alternatives:* interpolate between Census years; scale the state number by acreage share; model a county yield.
- *Why:* a filled-in value would sit next to measured ones with nothing to check it against. For withheld values USDA chose to hide exactly those numbers.
- *Cost:* the county story is untidy (each county has a different usable period).
- *Same rule for weather:* a feature is NA unless every day of its window was observed. An earlier version filled missing rain with 0 mm and counted days with no record as "no frost" (you flagged this). Cost: 36 of 140 county-years miss at least one value the dashboard shows, displayed as "missing".
- *This decision was yours*, made after discussing the options. It's a good interview story.

**Weather from NOAA stations, averaged.**
- *Alternatives:* gridded datasets (e.g. PRISM, NASA POWER, ERA5), which give uniform coverage with no station changes. **I did not evaluate these.**
- *Why stations:* the brief named them; the API is free.
- *Weak spot:* big. See 5.2 (station mix changes over time, and averaging dilutes frost).

**Calendar-window features (Jan–Mar "bloom", May–Aug "growing").**
- *Why:* from the brief; standard-sounding agronomy.
- *Weak spot:* see 5.2. NASS labels each season by its **end** year, so the windows are offset by about a year from the crop they're matched to. I did not check this until writing this document.

**Models: ARIMA + LightGBM, judged against a naive baseline.**
- *Alternatives:* drift, regularized linear regression or ARIMAX (better suited to 35 rows than boosted trees), tuned or other boosted models.
- *Why:* ARIMA and LightGBM came from the brief. The naive baseline ("repeat last year") and the rolling-origin evaluation were added afterward, because a model is only useful if it beats that.
- *Result:* neither model beats the baseline (5.3). Remaining weak spots: a small sample, no tuning, and I did not try the alternatives listed.

**Physical-bounds outlier filter.**
- *Alternatives:* statistical rules (z-score, IQR); manual removal.
- *Why:* transparent and defensible ("a 115 F daily high isn't real in Florida"). It removed 12 of 281,395 county records and none of the statewide ones.
- *Weak spot:* the bounds are my judgment, not derived.

**Four counties.**
- *Alternatives:* strictly the top four by acreage; all seven in the brief.
- *Why:* Polk, Hendry, DeSoto, and Highlands are large producers from the brief's list. Hardee actually ranks 4th among published 2022 totals (37,623 acres) but wasn't on the list; Highlands' 2022 total is withheld so its rank is unknown. The README says this plainly.

**Fail loudly, no fallback data.**
- *Alternatives:* keep the synthetic fallback so the pipeline "always works".
- *Why:* a fallback that produces plausible fake data mislabeled as real is worse than a crash. You made this call ("let's stop here... get the actual data"). Both fetchers now share one fail-loud client, and API keys come from environment variables rather than the code.

**Stress-score weights/thresholds.**
- From the brief, not fitted. Nothing in the repo shows the score tracks yield (5.4).

**Scenario tab: illustrative only.**
- The 2,000 lb/acre per frost day and the 50,000 acres are assumptions; the slider scales the 35-year average (0.77 frost days/yr), not the latest year. The README explains the framing.

**Dash on Render.**
- Brief said Dash; Render instead of Hugging Face Spaces was your choice. Static CSVs are committed so the app needs no database or secrets.

---

## 4. Problems hit and how they were fixed

Git hashes are given where the history shows it. Items marked *(not in history)* were fixed before the first commit or were debugging dead ends. Items marked *(pending commit)* are in the working tree and not yet committed.

| # | Problem | Cause | Fix |
|---|---|---|---|
| 1 | NASS returned 404, then 400 for every query | Wrong path (`/api/get` instead of `/api/api_GET/`); commodity `CITRUS` doesn't exist; double-underscore operators | Rewrote the query. First commit `4623a87` had the bugs; fixed in `1799062`. |
| 2 | NASS looked like it returned only `None` values | Reading `value` instead of `Value` (capital V) *(debugging scripts; not in history)* | Used the right key. Documented in `docs/API_SOURCES.md`. |
| 3 | No county yield exists | Not published at county level in any NASS source | Redesigned around statewide yield (`1799062`). |
| 4 | NOAA returned empty results | Used the `access/services/data/v1` endpoint | Switched to CDO v2 `/data`: token in a header, `GHCND:` station prefix, <1 year per request, paging (`1799062`). |
| 5 | Wrong weather stations | The "Lakeland" ID was actually Daytona Beach; Bartow is registered but has no data | Verified each station by requesting real observations across years (`1799062`). |
| 6 | Weather features were nonsense | Code decoded values as tenths (÷10) that the API didn't send; frost threshold was `<= 0` (a Celsius leftover) instead of `<= 32` F | Removed decoding, fixed threshold (`1799062`; present in `4623a87`). |
| 7 | Training crashed on save | LightGBM importances are numpy `int32`, not JSON-serializable | Cast to `int` (`1799062`). |
| 8 | **Fake data presented as real** | `fetch_data.py` silently generated synthetic data when an API failed, labeling the yield `NASS`. Synthetic CSVs were committed and public. | Real data replaced it (`1799062`); the fallback code was deleted and fetching now fails loudly (`b2b2d4c`). The synthetic data **remains in git history** (`80ee3fe`). |
| 9 | Render deploy crashed with `FileNotFoundError: data/df_model.csv` | `.gitignore` excluded the CSVs the app loads at import | Force-added the files (`80ee3fe`, `3f4f3c3`); documented in `RENDER_DEPLOYMENT.md`. |
| 10 | Dash wouldn't start | `app.run_server` was renamed `app.run` *(not in history)* | Updated. |
| 11 | Scenario slider did nothing | Scaled the latest year's frost days (0 in 2024; median is 0 across all years); 0 x any % = 0 | Scale off the 35-year average (`33af656`). |
| 12 | Comparison chart unreadable | Frost days (0–14), temperature (~90), and GDD (~4,000) in one bar chart; zero-frost years looked broken; labels clipped | Separate subplots, explicit value labels, extra axis headroom (`33af656`). |
| 13 | Sensor errors in county data | e.g. 115 F daily high, 101 F daily lows from co-op stations | Added the physical-bounds filter; 12 records removed (`33af656`). |
| 14 | **Overview KPI cards were hardcoded fiction** | Placeholders (28,000 lb/acre, a "2025 forecast", "HIGH") from the first commit | Computed from data; the nonexistent forecast removed (`b2b2d4c`). |
| 15 | **4 of 20 county acreage values were wrong** | A county-year returns several rows (ALL CLASSES plus single varieties). Where USDA withheld the total, the code took the first published row, a single variety, as the county total. | Request only the ALL CLASSES total; require exactly one row; record `(D)` as `withheld`; chart shows gaps (`d18827c`). This invalidated an earlier headline ("41% decline"). |
| 16 | README claimed things the code didn't do | "SHAP", "walk-forward CV", "frost days #1", fake model results | Rewrote README/docs from verified numbers (`64ac3f7`), later adding the withheld-data section (`a15db3f`). |
| 17 | **Missing weather counted as zero** | `fillna(0)` on rain; days with no record counted as "no frost"; GDD and frost sums over partial windows; "30-day" rolling windows stretched across gaps. Visible on the dashboard: 2024 showed "0 frost days" for three counties whose winter data was incomplete (I had said those zeros were real; that was wrong for those three). | You flagged the `fillna(0)`. Features are now NA unless the whole window is observed, from one shared function; the dashboard shows breaks and italic "*missing*". |
| 18 | County weather fetch could skip failed requests silently | `except Exception ... break`; also fetched Sebring twice and duplicated the outlier filter | Shared fail-loud client and filter, each station fetched once, a coverage check, nothing written on failure; verified by a clean end-to-end run on Python 3.14. |
| 19 | No naive baseline; evaluation was two test points | The brief specified the two models and a 2023–24 holdout | Added the baseline and a 17-fold rolling-origin evaluation. Neither model beats the baseline. |
| 20 | Dependencies unpinned; API keys in source | `>=` version ranges; credentials as constants (and in history) | Pinned to the live deployment's versions and tested in a clean Python 3.14 environment; keys read from environment variables. The old keys remain in git history. |
| 21 | NOAA data changed between two fetches | NOAA backfilled 27 missing February 2018 days at Lakeland Linder (81 rows) between 2026-09-16 and 2026-10-14; no existing value changed | Documented; kept the 2026-09-16 snapshot so the statewide and county files (which share that station) stay consistent. |

The pattern worth naming in an interview: several of these (#8, #14, #15, #16, #17) were **plausible-looking wrong outputs, not crashes**. They were caught by checking output against the source, not by errors.

---

## 5. Honest status

### 5.1 Real vs synthetic data
- **Everything currently committed is real**: NASS yield, NOAA weather, Census acreage. Re-fetching reproduces the files exactly (verified), apart from the NOAA backfill below.
- **It is a snapshot from 2026-09-16.** Upstream data can change: by 2026-10-14 NOAA had added 81 Lakeland Linder records (27 days of February 2018) with no existing value changed. They affect no feature, and the committed snapshot was kept so the statewide and county files stay consistent. A future refresh would change the files slightly and shift quoted numbers, so refresh deliberately and re-run everything.
- **Synthetic data existed and is still in git history** (`80ee3fe`, a public repo). The synthetic yield was labeled `NASS`. No code path generates synthetic data any more.
- **The pipeline stops at 2024.** NASS now has 2025 (73 boxes/acre = 6,570 lb) and 2026 (102 = 9,180) values, plus a 2027 forecast. "Latest status" on the dashboard is stale. The cutoff came from the brief, not a reason.

### 5.2 What the features really measure (accepted approximations, now disclosed)

This is a **scope decision**: the weather is approximate, and a station-consistent or gridded-weather study would be a different, much deeper project. That's a defensible position *if you say it first*. The station timeline and the year-label offset are now stated in the README's Known limitations and in `docs/METHODOLOGY.md`, so an interviewer won't be the one to discover them. What you can't do is present these inputs as precise, so the two README claims that leaned on them have been softened (see 5.8). A good one-line answer: *"The weather is a regional approximation built from a changing set of stations. I documented that and didn't read much into frost-based findings."*

**a) The statewide weather series is built from a changing set of stations.** Verified from the committed data:

| Years | Stations reporting Jan–Mar TMIN |
|---|---|
| 1990–1995 | Lakeland + Tampa |
| 1996–1998 | **Tampa only** |
| 1999–2007 | Orlando + Tampa |
| 2008–2011 | Orlando + Sebring + Tampa |
| 2012–2024 | all four |

I asked NOAA directly: Lakeland Linder has **0 records for 1996–2010** and Orlando Executive **0 before 1998**. This is real absence, not a fetch bug. But the comment in `src/fetch_data.py` ("all three cover 1990-2024 continuously") is **false**.

**b) Station choice swings frost numbers a lot, and averaging hides frost.** Mean Jan–Mar frost days per year, 2011–2019: Sebring 1.78, Lakeland 1.12, Orlando 0.33, Tampa 0.22. The repo's series (average TMIN across stations, *then* test ≤ 32 F) gives **0.44**. In 2012, one station had 5 frost days while the repo's series shows 1. So `frost_days_bloom` is both diluted and shifts with station mix. The finding "frost days weren't a leading predictor" therefore **isn't reliable evidence either way**.

**c) County comparisons have the same problem.** 41 of 140 county-years have only one station reporting Jan–Mar TMIN. Average stations per county went Polk 1.7 → 4.0, Hendry 2.0 → 1.0, Highlands 1.0 → 1.6 between the 1990s and 2020s. The README's Highlands-vs-Polk comparison (2.5 frost days a year over Highlands' 25 complete years vs 0.8 for Polk) is partly a **station-mix artifact**, not clean geography. Don't present it as a geographic finding.

**d) The year label is offset from the weather windows.** Verified from NASS records: `year=2023` has a forecast issued in October 2022 and holds the **2022–23 season** (including Hurricane Ian). NASS labels a Florida citrus season by its end year. The code matches calendar-year weather to that label. The crop labeled 2023 bloomed in spring 2022 and grew through summer 2022, so the May–Aug features describe the *next* crop's development, and "bloom" frost (Jan–Mar) for year Y mostly measures harvest-season freeze exposure of crop Y. The impact on results is **unchecked**; I'd expect it to add noise, not create a false signal.

**e) Smaller issues:**
- **Fixed: missing rain was counted as zero, and rolling windows counted observation days.** Features are now NA unless the whole window is observed, and rolling windows run over calendar days. The statewide series is complete; in the county panel 36 of 140 county-years miss at least one value the dashboard shows, 19 miss rainfall (worst: Highlands 2022, 9 of 123 days), and they display as "missing".
- `precip_deviation` is `precip_total_grow` minus a constant (the brief's "drought/wet signal"), so it's redundant for the models (importance 0; `precip_rolling_90` is also 0). It matters only in the stress score, which uses its absolute value. Its mean uses the whole series including the holdout; trees ignore a constant shift, so there's no practical leakage. Documented in the README.
- `temp_variance_grow` is a standard deviation, not a variance. The name came from the brief and was kept; the README now says so.

### 5.3 Modeling status
- **A naive baseline is now in the repo.** On the 2023–24 holdout, predicting last year's actual yield scores RMSE **4,834**; repeating 2022 for both years (same information as ARIMA) scores **5,704**. Both beat ARIMA (5,860) and LightGBM (10,457).
- **The rolling-origin evaluation agrees** (17 one-step folds, 2008–2024, equal information for every method). RMSE: naive **4,222**, ARIMA **4,290**, LightGBM **6,782**; last five years 3,580 / 3,767 / 7,385. LightGBM over-predicted in every year from 2010 on. **Neither model beats "repeat last year's yield."** Caveats: 17 overlapping folds is small; ARIMA failed to converge cleanly in 1 of 17 fits; its rolling numbers move ~1 lb/acre between statsmodels versions.
- **ARIMA essentially persisted.** Its holdout forecasts (11,902; 11,798) are about the 2022 value (11,700); the README now says so.
- **The 2023–24 holdout isn't like-for-like.** ARIMA forecasts both years from data through 2022. LightGBM's 2024 row uses the *actual* 2023 yield as `yield_lag1`, and it still predicted 16,548. The rolling-origin evaluation removes that mismatch.
- **Why LightGBM missed (partly verified):** 2023–24 yields are below anything in training (min 11,250), and the 2023–24 weather features look ordinary (0 frost days, TMAX ~92 F, GDD ~4,040), so there's no weather signal pointing down. In a re-fit for this walkthrough (slightly different settings, so its baseline is RMSE 10,892 rather than the repo's 10,457), loosening the leaf-size limit from 10 rows to 1 made it *worse* (12,232), so the small-dataset leaf constraint is not the explanation. The cause looks like the missing signal, not a fixable setting.
- **Still thin.** At most 32 training rows, no hyperparameter tuning, no prediction intervals, and none of the alternatives in section 3 (regularized linear model, ARIMAX) were tried. The old misnamed `fit_lightgbm_wfcv` is now `fit_lightgbm_holdout`.
- **Feature importance is split counts**, not SHAP (the script's printed label now says so).

### 5.4 Derived numbers that aren't validated
- **Stress score:** Spearman correlation with same-year yield change is **0.05** (with next-year change 0.11; computed for this walkthrough). Its "normal-year" baseline is 0.2, from the GDD term alone. The frost 75th-percentile threshold is **1.0** (median is 0), so two frost days saturates the frost term. The 0.1 yield flag is on in 12 of 35 years, all since 2014 except 2007, so it works as a "recent decline" marker. It scored the record-low 2023 as LOW (0.36). It's a weather-conditions gauge with no demonstrated link to yield.
- **Scenario dollars** rest on the 2,000 lb/acre and 50,000-acre assumptions. At +50%: 7,020 → 6,249 lb/acre, ~$17.4M. A sense of scale, not a forecast.

### 5.5 Untested or unverified paths
- **No automated tests.** Verification was manual: re-running scripts, comparing outputs to the APIs and to the committed files, and checking the dashboard in a browser. This is the largest remaining gap.
- **Both fetchers are fail-loud and were tested.** Missing keys (both scripts) and bad credentials (`fetch_data.py`) exit non-zero, write nothing, and print no key. The county fetch ran end to end on Python 3.14, the first full run of its current code; it reproduced the committed data apart from the NOAA backfill (5.1).
- **The pipeline was verified on Render's stack locally, not on Render.** Features and holdout results reproduced exactly on Python 3.9/pandas 2.0 and on Python 3.14/pandas 3.0 (the live site's versions); rolling ARIMA differs by ~1 lb/acre. `requirements.txt` is now pinned to the live versions and installed in a clean 3.14 environment. Not yet done: the pinned file deploying on Render (it will build on the next push). The live service ran Python 3.14 even though `render.yaml` said 3.12, so it apparently isn't driven by that file; set `PYTHON_VERSION` in the Render dashboard to fix it explicitly.
- **Dashboard changes were checked by hand in a browser** (gaps, italic "missing", default year, no console errors), not by automated tests.

### 5.6 Stubs, dead code, misnomers
- `src/app.py`: docstring says "3 tabs" (there are 4); `get_current_year_data()` is never called; unused imports (`px`, `np`, `State`, `Path`); `make_subplots` imported at the bottom under a "Placeholder" comment; the scenario floor `max(..., 5000)` is arbitrary; a variable named `acres_polk` holds a generic 50,000. Four callbacks (yield chart, stress chart, weather chart, feature importance) take the `tabs` value as their input, so they re-run on every tab switch; wasteful but harmless.
- `src/stress_indicator.py`: ends with "Next: Run src/build_dashboard.py", a file that doesn't exist. Its docstring mentions "lag-1 yield" but the code uses the *same-year* yield.
- Cleaned up in this round: the misnamed `fit_lightgbm_wfcv` and its dead variables, the negative "improvement" print, the "SHAP-like" label, the unused imports and "30-year mean" comment in `feature_engineering.py`, the duplicated outlier filter in the county fetcher, and the unused `geopandas`/`shapely` requirements.

### 5.7 Data limits that are permanent
- No county yield, production, or sales exists to find.
- Four county acreage totals are withheld by USDA (Hendry 2002 and 2007, DeSoto 2012, Highlands 2022). Hendry and Highlands each cover only part of 2002–2022.
- Clewiston (a Hendry station with real 1990–2003 data) isn't used; I first dismissed it after testing outside its date range.

### 5.8 Security, hygiene, and inaccuracies in the public repo

- **API keys are no longer in the code** (both fetchers read the `NASS_KEY` and `NOAA_TOKEN` environment variables), but the old values **remain in git history** of a public repo. Both are free public-data keys, so the realistic risk is low (someone burning your NOAA quota would break rebuilds, not the live site); rotating them is optional. Your email is also in git history from earlier docs.
- **Inaccuracies found in this review: now corrected** (in the working tree; commit pending):
  1. **README, "Model results"**: said ARIMA "extrapolates part of the way down". Now says its forecasts stayed close to the last training value, effectively repeating the last observation. (5.3)
  2. **`src/fetch_data.py` comment**: said all three stations cover 1990-2024 continuously. Now states the real gaps. (5.2a)
  3. **README** "Frost exposure differs sharply by county": softened; notes part of the gap reflects each county's stations. (5.2c)
  4. **README** "Frost days were not a leading predictor": now "ranked 7th of 12" and calls it weak evidence given approximate inputs. (5.2b, d)
  5. **README / `docs/METHODOLOGY.md`**: now include the station timeline, the frost-dilution numbers, and the season-label offset. (5.2a, d)
  6. **`docs/API_SOURCES.md`** stations table: now says catalog ranges are not actual coverage.

### Done in this round (working tree; commit pending)
Naive baseline and rolling-origin evaluation; both fetchers fail-loud with a shared client and filter; `requirements.txt` pinned and tested on Python 3.14; keys moved to environment variables; missing weather treated as NA instead of zero; `temp_variance_grow` and `precip_deviation` documented.

### Still open (optional, in order of value)
1. Automated tests (even a few: the feature function on a tiny fixture with a missing day, `is_plausible`, the acreage "exactly one row" rule).
2. Set `PYTHON_VERSION` in the Render dashboard, and check the first build with the pinned `requirements.txt` after pushing.
3. Try a model that suits 35 rows (regularized linear regression or ARIMAX) against the naive baseline.
4. Rotate the two API keys (optional; they remain in git history).

---

## 6. Likely interview questions

### Technical

**1. Your LightGBM did worse than ARIMA. Why, and how much should I trust that comparison?**
> On the 2023–24 holdout both missed badly (RMSE 5,860 and 10,457 lb/acre), and I wouldn't trust that comparison alone: it's two test points and the methods got different information (ARIMA forecast two steps ahead; LightGBM's 2024 row used the actual 2023 lag). So I added a naive baseline ("repeat last year's yield") and a rolling-origin evaluation over 17 one-step folds (`rolling_origin_evaluation` in `src/train_models.py`), where every method sees the same information. There the baseline scores RMSE 4,222, ARIMA 4,290, and LightGBM 6,782: neither model beats the baseline, and LightGBM over-predicted every year from 2010 on. The likely reason is the signal: 2023–24 yields sit below anything in training, and those years' weather looks ordinary, so nothing in the weather points down. With only 35 rows, my next step would be a regularized linear model or ARIMAX rather than boosted trees.

**2. Walk me through how you built the weather features. What could go wrong with them?**
> Daily station data is averaged across stations, then I compute frost days (TMIN ≤ 32 F, Jan–Mar) and growing-season stats (May–Aug), merged to yield by year (`src/feature_engineering.py`, one shared function for statewide and county). A feature is only calculated when every day of its window was observed; otherwise it's left missing, because an earlier version counted missing rain as zero and unrecorded days as "no frost", which made incomplete years look dry and frost-free. Three problems remain: the set of stations changes over time (Lakeland has no data 1996–2010, Orlando none before 1998), so the series isn't consistent; averaging TMIN before applying the threshold dilutes frost (2011–2019: Sebring 1.78 frost days/yr vs the averaged series 0.44); and NASS labels a season by its end year, so my calendar-year windows are offset by about a year from the crop's actual bloom and growth. The weather is a regional approximation, and I documented these limits in the README and methodology rather than treating the weather as precise, so I don't read much into the frost-based findings. A station-consistent or gridded-weather study would be a separate project.

**3. County yield isn't published. What did you do, and why not estimate it?**
> I confirmed against the API that NASS publishes county acreage but no county yield or production, in either the survey or Census programs, so I modeled statewide yield and used counties only for what is real: local weather and Census bearing acreage. Four of 20 county acreage totals are withheld by USDA; I left them blank and show gaps in the chart (`fetch_bearing_acreage()`, `connectgaps=False`). I didn't impute because the value would be a model output displayed beside measured data, with nothing to validate it against, and three of the four gaps sit at the ends of a series, so filling them would be extrapolation. The cost is that the county trends cover different periods, and I say so.

**4. How do you know the data pipeline is correct?**
> Mostly by checking outputs against the source rather than trusting that code ran. A fresh re-fetch reproduces the committed data, a re-run of features and training reproduces the committed results on both Python 3.9/pandas 2 and the live site's Python 3.14/pandas 3, and I tested that a missing or bad API key stops the run and writes nothing. That approach caught real errors: four county acreage values were single orange varieties mistaken for county totals (I now require exactly one all-classes row), missing weather was being counted as zero, and the first version silently substituted fake data when an API failed. It also showed upstream data moving: NOAA backfilled 81 records between two fetches, so I treat a fetch as a dated snapshot. The honest gap is that there are no automated tests; verification was manual.

**5. What does your stress score actually tell me?**
> It's a weather-conditions index: 0.4 x frost + 0.3 x rain deviation + 0.2 x inverse GDD + 0.1 x a low-yield flag, using thresholds from 1990–2020 (`src/stress_indicator.py`). The weights and thresholds came from the project brief, not a fit, and I haven't validated it: its rank correlation with yield change is about 0.05. It scored 2023, the record-low year, as LOW because disease and hurricane damage aren't in its inputs. I'd present it as a descriptive gauge of frost/rain/heat conditions, not a risk predictor.

### Behavioral

**1. Tell me about a time you found a mistake in your own work.**
> While checking a claim that four counties were the "top four" by acreage, I verified the underlying county data and found four of my twenty acreage values were not county totals: where USDA withheld a total, my code had picked up a single orange variety instead (`d18827c`). It had produced a fake dip in one county's chart and an overstated decline in another. I fixed the fetcher to accept only the all-varieties total, regenerated the data, replaced the headline with figures computed from published totals only, and added a section to the README on missing and withheld data. The lesson I took: outputs that look plausible need checking against the source.

**2. Tell me about a time you chose the harder or more honest option.**
> Early on the APIs failed and the quick path was to deploy with synthetic data, which looked fine. I chose to stop, debug the actual APIs (wrong endpoints, wrong station IDs, a unit-decoding bug), and use real data. Later, when county yield turned out to be unpublishable, I chose to leave withheld values blank instead of estimating them, and to report that my models missed the 2023–24 collapse rather than tune until they didn't. The result is a less impressive-looking project that I can defend line by line.

**3. You built this quickly with AI assistance. How do I know you understand it?**
> I used an AI assistant heavily for implementation, and I'd say so plainly. What I own is the direction and the checks: I rejected synthetic data, decided how to handle withheld values, and questioned claims I couldn't verify, like the county selection. I then re-read the whole repo and re-ran the key checks before an interview like this. I can explain every stage, and I know where it's weak: a small evaluation sample, a changing station set, season-label misalignment, no automated tests, and a naive baseline that my models don't beat. *(Before using this answer, make sure it's true for you: be ready to explain any file or function in the repo. Work through `src/feature_engineering.py` and `src/train_models.py` line by line first.)*
