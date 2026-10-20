# API Sources and Notes

How this project queries USDA NASS and NOAA, plus the non-obvious behaviors that cost time to discover. API keys are free; export them as the `NASS_KEY` and `NOAA_API_KEY` environment variables (`NOAA_TOKEN` is accepted as an alternative name for the NOAA key). Both fetch scripts read them at run time and stop with a clear message if they are unset; no key is stored in the code.

## USDA NASS QuickStats

Docs: <https://quickstats.nass.usda.gov/api>

Statewide yield query (`src/fetch_data.py`):

```
GET https://quickstats.nass.usda.gov/api/api_GET/
  key=<NASS_KEY>  commodity_desc=ORANGES  state_alpha=FL  agg_level_desc=STATE
  statisticcat_desc=YIELD  unit_desc=BOXES / ACRE  class_desc=ALL CLASSES
  util_practice_desc=ALL UTILIZATION PRACTICES  year__GE=1990  year__LE=2024  format=json
```

County bearing-acreage query (`src/fetch_county_data.py`): `commodity_desc=ORANGES`, `county_name=<POLK|HENDRY|DE SOTO|HIGHLANDS>`, `source_desc=CENSUS`, `year=<2002|2007|2012|2017|2022>`, `statisticcat_desc=AREA BEARING`, `unit_desc=ACRES`.

Things to know:

- **The path is `/api/api_GET/`.** `/api/get` returns 404.
- **Operators use double underscores:** `year__GE`, `year__LE`.
- **Commodity names must match exactly.** There is no plain `CITRUS`; use `ORANGES` or `CITRUS TOTALS`. List valid values with `/api/get_param_values/?key=...&param=commodity_desc`.
- **The value field is `Value` (capital V).** Reading lowercase `value` silently yields nothing. Suppression codes such as `(D)` can arrive padded with whitespace.
- **Citrus yield and production exist only at state level.** County-level rows for oranges and citrus totals cover area statistics only, in both the survey and Census programs. The only yield unit is `BOXES / ACRE` (no `LB / ACRE`), converted here at 90 lb/box.
- **One county-year returns several rows.** Besides `class_desc=ALL CLASSES` there are single-variety rows (`VALENCIA`, `MID & NAVEL`) and other domain rows, and their order is not guaranteed. Always filter `class_desc=ALL CLASSES` and `domain_desc=TOTAL`; taking "the first published row" can silently return a single variety that looks like a county total (this happened in an earlier version of this project and was fixed).
- **`(D)` means withheld**, not zero or missing: NASS withholds the value to avoid disclosing individual operations' data. A total can be `(D)` while a single variety under it is published.
- **County names follow NASS spelling:** DeSoto County is `DE SOTO`; `DESOTO` returns HTTP 400.
- **An invalid parameter combination returns HTTP 400** (`bad request - invalid query`) without saying which parameter is wrong. Narrow the query to find it.

## NOAA CDO v2

Docs: <https://www.ncei.noaa.gov/cdo-web/webservices/v2>

```
GET https://www.ncei.noaa.gov/cdo-web/api/v2/data        (header: token: <NOAA_API_KEY>)
  datasetid=GHCND  stationid=GHCND:<id>  startdate=YYYY-01-01  enddate=YYYY-12-31
  datatypeid=TMAX,TMIN,PRCP  units=standard  limit=1000  offset=1
```

Things to know:

- **The token goes in a `token` header**, not the query string.
- **Station IDs need the `GHCND:` prefix** and the dataset is `GHCND`.
- **Each request must span less than one year** (otherwise HTTP 400). The fetchers loop year by year.
- **Results are paged at 1,000 rows;** `offset` starts at 1. A full year of three variables at one station is about 1,095 rows, so most station-years need two requests.
- **`units=standard` returns TMAX/TMIN in degrees F and PRCP in inches**, already decimal (no tenths decoding).
- **Documented limits are 5 requests/second and 10,000/day** per token; the fetchers sleep 0.2 s between requests.
- **The newer `access/services/data/v1` endpoint (`global-summary-of-the-day`) returned empty results** for every station tried here and is not used.
- **The station catalog is not evidence of data.** In our tests `/datatypes` ignored the `datatypeid` filter and returned a truncated list, and registered date ranges did not guarantee observations exist. Bartow Municipal (`USW00012809`) is registered from 1955 but returned no observations in any year tested (1990-2024). Confirm a station by requesting actual observations across several years inside its registered range; `src/station_coverage.py` does this for every candidate.
- **Find a station's county with `/stations?locationid=FIPS:<county>`.** Station names mislead: Moore Haven Lock 1 is listed under Glades County, not Hendry; Tampa International under Hillsborough; Orlando Executive under Orange; Punta Gorda Airport under Charlotte.
- **IDs are easy to mix up:** `USW00012834` is Daytona Beach International, not Lakeland.
- **Co-op (`USC`) stations contain isolated sensor errors** (e.g. a 115 F daily high, 101 F daily lows). Both fetchers apply the plausibility filter described in `docs/METHODOLOGY.md`.
- **Requests fail loudly.** Both `fetch_data.py` and `fetch_county_data.py` share one client (`get_json`) that retries three times, then stops and writes nothing; neither has a substitute-data fallback. A year with no observations at a station is legitimate (stations start and stop): it is reported and left blank, not an error. A county station with data in fewer than 20 years is treated as a wrong station id and stops the run.
- **Published data can change.** NOAA backfilled 27 missing days of February 2018 at Lakeland Linder between two fetches a month apart, with no existing values altered (that station is no longer used). Treat a fetch as a snapshot of that date.

## Stations used

Catalog date ranges are not actual coverage. For observed coverage by year, see `data/station_coverage_matrix.csv` and the table in [METHODOLOGY.md](METHODOLOGY.md#weather-stations). Counties are from NOAA's station metadata.

| Station | ID | County | Used for |
|---|---|---|---|
| Tampa International | USW00012842 | Hillsborough | Statewide model (fixed pair) |
| Archbold Biological Station | USC00080236 | Highlands | Statewide model (fixed pair); Highlands panel |
| Lakeland 2 | USC00084802 | Polk | Polk panel |
| Moore Haven Lock 1 | USC00085895 | Glades | Hendry panel (nearest usable station; see METHODOLOGY) |
| Arcadia | USC00080228 | DeSoto | DeSoto panel |

Probed but not used (coverage in `data/station_coverage_matrix.csv`): Lakeland Linder (`USW00012883`), Orlando Executive (`USW00012841`), Sebring (`USW00092827`), La Belle (`USC00084662`), Punta Gorda Airport (`USW00012812`), Avon Park 2 W (`USC00080369`), Bartow 1 SE (`USC00080478`), Lake Alfred (`USC00084707`), Mountain Lake (`USC00085973`), Winter Haven (`USC00089707`) and Gilbert Airport (`USW00012876`), Big Cypress (`USC00080737`), Clewiston (`USC00081654`) and Clewiston No. 2 (`USC00081651`), Devils Garden (`USC00082298`). The first four were the earlier version's statewide stations; the earlier county stations included La Belle, Punta Gorda Airport and Avon Park 2 W.

## Another source: FAWN

The University of Florida's Florida Automated Weather Network (FAWN) publishes open daily-summary CSVs by year (1997 onward) and by station at `https://fawn.ifas.ufl.edu/data/fawnpub/daily_summaries/`, with stations in growing areas (for example Lake Alfred, Frostproof, Arcadia, Sebring, Clewiston). It was assessed on 2026-10-20 and not used: it starts in 1997, years are not complete for many stations (Lake Alfred has a complete bloom window in 21 of 28 years, Arcadia 16, Clewiston 14), and the files have several header formats, split-year files, sentinel values such as -6999, and implausible readings (-63 C). Temperatures are in C and rain in inches. It could be added later for the county panels.
