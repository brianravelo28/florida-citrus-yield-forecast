# Data Schema

All files are CSVs in `data/`. Temperatures are degrees F; raw precipitation is inches; engineered precipitation features are millimetres (inches x 25.4). All were pulled on 2026-11-03.

## Raw data

### `data/citrus_by_state.csv` - 2,483 rows (1990-2026)

One row per fruit, state, year and measure, from NASS state surveys (`src/fetch_industry_data.py`). Forecast rows for the coming season are dropped.

| Column | Description |
|---|---|
| `fruit` | Oranges, Grapefruit, Tangerines, Lemons, Tangelos |
| `state` | `FL`, `CA`, `TX`, `AZ` (a fruit appears only in the states and years NASS publishes it) |
| `year` | NASS season, labeled by its end year (2023 is the 2022-23 season) |
| `measure` | `bearing_acres` (acres), `yield_boxes_per_acre`, `production_boxes` (utilized boxes), `production_tons` (utilized tons, recent years only), `value_of_production_usd` (nominal dollars, packinghouse-door equivalent), `price_usd_per_box` (marketing year, packinghouse-door equivalent) |
| `value` | The published value. **Blank when NASS withheld it or marked it not available** |
| `note` | Empty, or why the value is blank: `withheld (D)` or `not available (NA)` |
| `status` | `reported`, or `preliminary` for the season ending in 2026 (NASS's August estimate, revised a year later) |

Blank values: 63 of 2,483 (48 withheld, 15 not available). A value is never estimated. One published value is flagged by the dashboard but not changed: `yield_boxes_per_acre` for California oranges in 2022 (58), which conflicts with NASS's own production and acreage (see [METHODOLOGY.md](METHODOLOGY.md#checks-on-the-data)).

### `data/county_acreage.csv` - 20 rows

| Column | Description |
|---|---|
| `county_name` | Polk, Hendry, DeSoto, Highlands |
| `year` | Census year: 2002, 2007, 2012, 2017, 2022 |
| `bearing_acres` | Orange bearing acres, all varieties combined (USDA Census of Agriculture). **Blank when USDA withheld the total** |
| `status` | `published` (16 rows) or `withheld` (4 rows: Hendry 2002 and 2007, DeSoto 2012, Highlands 2022). `withheld` means the Census marked the total `(D)`: withheld to avoid disclosing individual operations' data |
| `data_source` | `NASS_CENSUS` |

Withheld values are never estimated. For those four rows USDA still published one single variety, which is not a county total and is not used.

### `data/census_orange_acres_by_county.csv` - 215 rows

Bearing orange acres for every Florida county with a Census record, by Census year: `county_name`, `year`, `bearing_acres` (blank when withheld), `status` (`published` or `withheld`). Used to check the choice of the four panel counties (a test confirms the ranking).

### `data/county_weather.csv` - 145,820 rows

One row per station, day and variable, after the plausibility filter.

| Column | Description |
|---|---|
| `county_name` | The panel county the station serves (Polk, Hendry, DeSoto, Highlands) |
| `station_id`, `station_name` | GHCND station: Lakeland 2 `USC00084802`, Moore Haven Lock 1 `USC00085895`, Arcadia `USC00080228`, Archbold Biological Station `USC00080236` |
| `date` | `YYYY-MM-DD` |
| `datatype` | `TMAX`, `TMIN` (F) or `PRCP` (inches) |
| `value` | Observation |
| `data_source` | `NOAA` |

### `data/stations.csv` - 4 rows

| Column | Description |
|---|---|
| `station_id`, `station_label` | GHCND id and the short name used on the dashboard |
| `station_name_noaa` | NOAA's name for the station |
| `latitude`, `longitude` | From NOAA's station metadata |
| `noaa_mindate`, `noaa_maxdate` | NOAA's registered date range (a catalog range, not actual coverage) |
| `panel_county` | The county panel the station is used for |
| `county_noaa` | The county NOAA lists the station under (Moore Haven Lock 1 is `Glades`, used for the Hendry panel) |

## Engineered data

**Missing weather is blank, never zero.** `frost_days_bloom` needs every night of January-March observed; the May-August features need at least 95% of the window's days observed and are computed from the observed days (sums are not scaled up). Otherwise the feature is blank. Rules and rationale: [METHODOLOGY.md](METHODOLOGY.md#frost-and-weather-features).

### `data/county_features.csv` - 148 rows (4 stations x 37 years) x 16 columns

| Column | Description |
|---|---|
| `county_name`, `year` | Key (calendar year of the weather window) |
| `tmax_mean_grow`, `tmin_mean_grow` | Mean daily max/min temperature, May-August (F) |
| `frost_days_bloom` | Days with TMIN <= 32 F, January-March. Nullable integer: whole numbers with blanks |
| `precip_total_grow` | Total precipitation, May-August (mm) |
| `precip_rolling_30`, `_60`, `_90` | Largest 30/60/90-calendar-day precipitation sum within May-August (mm) |
| `temp_variance_grow` | **Standard deviation** (not variance) of daily max temperature, May-August (F) |
| `gdd_total_grow` | Sum of max(0, (TMAX+TMIN)/2 - 50), May-August |
| `bloom_days_missing`, `grow_days_missing` | Days of the January-March window with no TMIN, and the most days missing among TMAX, TMIN and PRCP in May-August. 91 or 90 means no record |
| `precip_deviation` | `precip_total_grow` minus that county's mean (mm) |
| `bearing_acres` | Census bearing acres; populated only for published totals (blank for withheld totals and non-Census years; never interpolated) |
| `acreage_status` | `published`, `withheld`, or blank for non-Census years, so withheld values can be told apart from years with no Census |

Blank counts out of 148: `frost_days_bloom` 30; `tmax_mean_grow`, `tmin_mean_grow`, `temp_variance_grow`, `gdd_total_grow`, `precip_total_grow` and `precip_deviation` 20; `precip_rolling_30` 20, `_60` 21, `_90` 30. 34 station-years are missing at least one of the frost, TMAX or GDD values the dashboard shows. Polk has no record before late 1995 and DeSoto none after April 2021, so those years are blank rows.

### `data/station_frost_summary.csv` - 4 rows

Bloom-season frost per station, counting only winters with every night observed: `county_name`, `years_in_range` (37), `years_counted`, `first_year_counted`, `last_year_counted`, `mean_frost_days`, `max_frost_days`, `max_frost_year` (the first such year when several tie), `trend_days_per_decade` (a straight-line fit through the counted winters).

## Station coverage

### `data/station_coverage.csv` and `data/station_coverage_matrix.csv`

Output of `src/station_coverage.py`: days of plausible TMAX / TMIN / PRCP observations per candidate station, year and month (`station_coverage.csv`: `station_name`, `station_id`, `year`, `month`, `datatype`, `days`), and per station-year for the two feature windows (`station_coverage_matrix.csv`: `station`, `year`, `bloom_tmin_days`, `bloom_days_needed`, `grow_tmax_days`, `grow_tmin_days`, `grow_prcp_days`).
