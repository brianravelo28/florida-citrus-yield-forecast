# Methodology

What the code does and why. Headline results are in the [README](../README.md); the numbers here are the supporting detail.

Terms: **NASS** (USDA National Agricultural Statistics Service); **NOAA** (National Oceanic and Atmospheric Administration); **GHCND** (Global Historical Climatology Network daily, NOAA's station dataset); **TMAX / TMIN / PRCP** (daily maximum and minimum temperature, and precipitation); **GDD** (growing degree days: heat accumulated above 50 F); **HLB** (huanglongbing, citrus greening disease).

## Scope

The project describes Florida orange yield, county acreage and winter frost by weather station. It builds no model and makes no forecast. Yield is published only statewide, so it is shown statewide; the county panels show Census bearing acreage and weather from one NOAA station per county.

## Data sources and pull dates

All files were pulled on 2026-11-03 and are real observations; none is synthetic. NOAA can backfill published data, and NASS revises its newest season a year later, so treat each pull as a snapshot of its date.

1. **Yield** (`src/fetch_data.py`): QuickStats `ORANGES`, `YIELD`, `BOXES / ACRE`, all classes, state level, 1990-2026, times 90 lb per box (the standard Florida orange box). The fetcher requires every year to be present. NASS labels a season by its end year: 2023 is the 2022-23 season. The season ending in 2026 is NASS's preliminary estimate (published August 2026), marked `status = preliminary`; all earlier seasons are `reported`.
2. **County acreage** (`src/fetch_county_data.py`): Census of Agriculture bearing orange acres, all varieties combined, 2002, 2007, 2012, 2017 and 2022. `src/fetch_county_ranking.py` fetches the same figure for every Florida county, to check the county choice.
3. **Weather** (`src/fetch_county_data.py`): daily TMAX, TMIN and PRCP from NOAA's Climate Data Online API. Readings outside plausible Florida bounds (TMAX 20-110 F, TMIN -5-85 F, PRCP 0-20 in) are dropped as sensor errors; this removed 7 of 145,827 records (Lakeland 2: 2, Arcadia: 4, Moore Haven Lock 1: 1).
4. **Station locations:** coordinates and county come from NOAA's station metadata, fetched with the weather (not typed by hand). The county is the Florida county whose NOAA station list contains the station.

## Counties and stations

**County choice.** Polk, Hendry, DeSoto and Highlands are the four largest Florida counties by bearing orange acres in the 2017 Census (66,988, 65,849, 46,935 and 40,799 acres), the latest Census in which all four have published totals. Hardee is fifth in 2017 (37,397) and fourth in 2022 (37,623, when Highlands' total is withheld), and is not included; its weather stations were not assessed. The ranking is computed from `data/census_orange_acres_by_county.csv` and checked by a test.

**One station per county.** Averaging several stations before counting frost days dilutes real frosts (a freeze at one station but not the others is smoothed away), and a station set that changes over time makes trends partly an artifact of which stations reported. One fixed station per county avoids both, at the cost that each series describes a station, not the county. Gaps stay blank; they are never filled from another station.

**How the stations were chosen.** `src/station_coverage.py` requested real observations (the NOAA catalog's date ranges are not evidence of data) for 20 candidate stations in and around the four counties, for each year of 1990-2026. For each county the station used is an in-county station with the fewest years missing a complete winter or growing season, with one exception (below). Years with a complete window, out of 37 (winter: every January-March TMIN night observed; growing season: at least 95% of May-August days observed for TMAX, TMIN and PRCP). The full counts are in `data/station_coverage_matrix.csv`:

| Station (county per NOAA) | Winter | Growing | Both | First-last year with data |
|---|---|---|---|---|
| **Archbold Biological Station** (Highlands) | 37 | 37 | 37 | 1990-2026 |
| Tampa International (Hillsborough) | 37 | 37 | 37 | 1990-2026 |
| **Lakeland 2** (Polk) | 29 | 30 | 28 | 1996-2026 |
| **Moore Haven Lock 1** (Glades) | 28 | 33 | 26 | 1990-2026 |
| Orlando Executive (Orange) | 26 | 28 | 26 | 1998-2026 |
| Mountain Lake (Polk) | 29 | 30 | 23 | 1990-2026 |
| **Arcadia** (DeSoto) | 24 | 26 | 21 | 1990-2021 |
| Punta Gorda Airport (Charlotte) | 19 | 25 | 17 | 1997-2026 |
| Big Cypress (Hendry) | 19 | 19 | 16 | 2002-2026 |
| Lakeland Linder (Polk) | 16 | 20 | 15 | 1990-2026 |
| Devils Garden (Hendry) | 16 | 22 | 14 | 1990-2018 |
| Avon Park 2 W (Highlands) | 13 | 18 | 10 | 1990-2022 |
| Bartow 1 SE (Polk) | 15 | 21 | 9 | 1990-2026 |
| Sebring (Highlands) | 4 | 18 | 4 | 2008-2026 |

Stations in bold are the four used. The table omits six further stations that reported fewer complete years than those shown (see the matrix file). Tampa reports every year but is in Hillsborough County, outside the four panel counties, so it is not used.

**The Hendry exception.** Hendry's own stations are blank in 20 or more of 37 years (Big Cypress and Devils Garden), so the panel uses the nearest usable station, Moore Haven Lock 1. NOAA's metadata lists it in **Glades County** (about 20 km from Devils Garden in Hendry). The dashboard labels it that way.

**Archbold is a cold site.** It sits in open scrub and averages 6.5 bloom-season frost days a year, against 1.0 to 3.8 at the other stations. Its counts are not representative of nearby groves.

## Frost and weather features

`src/feature_engineering.py` computes the features per station and year from the daily data (temperatures in degrees F, precipitation in mm):

| Feature | Definition |
|---|---|
| `frost_days_bloom` | Days with TMIN at or below 32 F, January-March |
| `tmax_mean_grow`, `tmin_mean_grow` | Mean daily maximum and minimum temperature, May-August |
| `temp_variance_grow` | **Standard deviation** (not variance) of daily maximum temperature, May-August; the name is kept so file and column names stay stable |
| `gdd_total_grow` | Growing degree days, base 50 F: the sum of max(0, (TMAX + TMIN)/2 - 50), May-August |
| `precip_total_grow` | Total precipitation, May-August |
| `precip_rolling_30/60/90` | Largest 30/60/90-calendar-day rolling precipitation sum within May-August |
| `precip_deviation` | `precip_total_grow` minus that county's mean |

**Missing weather is missing, never zero.** Filling missing rainfall with 0 mm, or counting days with no record as "no frost", would understate frost counts and sums. The rules are:

- **Frost days:** every night of January-March must be observed, because a missing night may have been a frost. Otherwise `frost_days_bloom` is blank.
- **May-August features:** computed from the observed days if at least 95% of the window's 123 days are observed (up to 6 missing); otherwise blank. Means and the standard deviation describe the observed days. Sums (`precip_total_grow`, `gdd_total_grow`) cover the observed days and are **not scaled up**, so they can be up to about 5% low in a year with gaps. Rolling rainfall maxima only use windows of consecutive observed days. The 95% cutoff is a practical choice, not a statistical standard.
- **Data-quality columns:** `bloom_days_missing` and `grow_days_missing` record how many days of each window had no observation.

Counts out of 148 station-years (4 stations x 37): `frost_days_bloom` blank in 30; the May-August features and `precip_deviation` blank in 20; `precip_rolling_90` in 30. 34 station-years are missing at least one of the frost, TMAX or GDD values the dashboard shows.

## Frost summary

`data/station_frost_summary.csv` (written by `src/county_feature_engineering.py`) counts only winters with every night observed, so stations have different numbers of counted winters. The trend is a straight-line fit through the counted winters, in frost days per decade; with 24 to 37 points it describes the data and is not a significance test.

| Station | Winters counted | Mean frost days | Most (year) | Trend per decade |
|---|---|---|---|---|
| Archbold (Highlands) | 37 of 37 (1990-2026) | 6.5 | 25 (2010) | +0.5 |
| Arcadia (DeSoto) | 24 of 37 (1990-2021) | 3.8 | 14 (2010) | -0.4 |
| Lakeland 2 (Polk) | 29 of 37 (1996-2026) | 1.8 | 5 (several winters) | -0.5 |
| Moore Haven Lock 1 (Hendry panel) | 28 of 37 (1990-2020) | 1.0 | 6 (2010) | 0.0 |

The dashboard headline says frost "stayed flat" only while every station's trend is within one frost day per decade; otherwise it says frost varied by station. Polk's 2010 winter, the coldest at the other stations, has too many missing nights to count, which lowers Polk's recorded maximum.

**Season labels.** NASS labels a Florida citrus season by its end year (2023 is the 2022-23 season), while frost is counted in the calendar months January-March of a year. The two are not aligned year by year, so the dashboard shows frost and yield in separate charts and does not overlay them.

## County acreage and withheld values

Bearing acreage comes from the Census of Agriculture every five years and is left empty in other years. Four of the 20 panel county-year totals are withheld by USDA (marked `(D)`): Hendry 2002 and 2007, DeSoto 2012, Highlands 2022. They are kept as blank rows with `status = withheld`, plotted as gaps, and named in the chart footnote, which is generated from the data. They are not estimated: a modeled value would sit beside measured ones, and since USDA withheld exactly these numbers there is nothing to validate an estimate against. For those rows USDA published a single orange variety instead (for example Highlands 2022: Valencia, 27,449 acres); that is not a county total, so it is not used. Trend statements use only each county's published totals (Polk 2002-2022, DeSoto 2002-2022, Hendry 2012-2022, Highlands 2002-2017).

**Why no county yield.** QuickStats has no county-level orange yield or production in any source: county rows for oranges and citrus totals are Census area statistics only. NASS's Citrus Summary publication lists county production, and states that those estimates are an apportionment of the final statewide harvest based on bearing trees, fruit per tree and drop and size surveys, so they are not county measurements. No county yield is shown or estimated.

## Reproducibility

API keys are read from the `NASS_KEY` and `NOAA_API_KEY` (or `NOAA_TOKEN`) environment variables; nothing is stored in the code. Every fetcher retries transient failures, then stops and writes nothing if any request fails, any Census acreage query returns other than exactly one row, a county station has data in fewer than 20 years, or NOAA lists no Florida county for a station. Years in which a station has no observations are reported and left blank.

What was run: all four fetch scripts and the feature step ran end to end on Python 3.14 / pandas 3.0 on 2026-11-03, and the committed data files are their output. Tests (`tests/`, run in CI on Python 3.13 and 3.14) cover the feature code, the frost summary, the helper functions and the committed data; they do not cover the API fetchers or the dashboard. `requirements.txt` is pinned and was installed in a clean Python 3.14 environment.
