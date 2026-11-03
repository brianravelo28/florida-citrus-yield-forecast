# API Sources and Notes

How this project queries USDA NASS and NOAA, plus the non-obvious behaviors that cost time to discover. API keys are free; export them as the `NASS_KEY` and `NOAA_API_KEY` environment variables (`NOAA_TOKEN` is accepted as an alternative name for the NOAA key). The fetch scripts read them at run time and stop with a clear message if they are unset; no key is stored in the code.

## USDA NASS QuickStats

Docs: <https://quickstats.nass.usda.gov/api>

Citrus by state query (`src/fetch_industry_data.py`), one request per fruit and measure:

```
GET https://quickstats.nass.usda.gov/api/api_GET/
  key=<NASS_KEY>  commodity_desc=<ORANGES|GRAPEFRUIT|TANGERINES|LEMONS|TANGELOS>  agg_level_desc=STATE
  source_desc=SURVEY  statisticcat_desc=<AREA BEARING|YIELD|PRODUCTION|PRICE RECEIVED>  unit_desc=<see below>
  year__GE=1990  year__LE=2026  format=json
```

Units used: `ACRES`, `BOXES / ACRE`, `BOXES` and `TONS` (production, utilization `UTILIZED`), `$, PHD EQUIV` (value), `$ / BOX, PHD EQUIV` (price, reference period `MARKETING YEAR`). The script then keeps `class_desc=ALL CLASSES` and `domain_desc=TOTAL` rows.

County bearing-acreage query (`src/fetch_county_data.py`; `src/fetch_county_ranking.py` runs the same query with `agg_level_desc=COUNTY` for every county): `commodity_desc=ORANGES`, `county_name=<POLK|HENDRY|DE SOTO|HIGHLANDS>`, `source_desc=CENSUS`, `year=<2002|2007|2012|2017|2022>`, `statisticcat_desc=AREA BEARING`, `unit_desc=ACRES`.

Things to know:

- **The path is `/api/api_GET/`.** `/api/get` returns 404.
- **Operators use double underscores:** `year__GE`, `year__LE`.
- **Commodity names must match exactly.** There is no plain `CITRUS`; use `ORANGES` or `CITRUS TOTALS`. List valid values with `/api/get_param_values/?key=...&param=commodity_desc`.
- **The value field is `Value` (capital V).** Reading lowercase `value` silently yields nothing. Suppression codes such as `(D)` can arrive padded with whitespace.
- **QuickStats has yield and production only at state level.** County-level rows for oranges and citrus totals cover Census area statistics only (`AREA BEARING`, `AREA NON-BEARING`); querying `PRODUCTION` or `YIELD` at county level returns HTTP 400. NASS's separate Citrus Summary publication does list county production, but states that it is an apportionment of the statewide harvest (by bearing trees, fruit per tree, and drop and size surveys), not a county measurement. The only yield unit is `BOXES / ACRE` (no `LB / ACRE`), converted here at 90 lb/box.
- **One county-year returns several rows.** Besides `class_desc=ALL CLASSES` there are single-variety rows (`VALENCIA`, `MID & NAVEL`) and other domain rows, and their order is not guaranteed. Always filter `class_desc=ALL CLASSES` and `domain_desc=TOTAL`; taking "the first published row" can silently return a single variety that looks like a county total.
- **The newest season is preliminary.** NASS loads the season ending in the current year (2026) as an August estimate and revises it a year later; `src/fetch_industry_data.py` marks it `status = preliminary`.
- **`year__LE` does not exclude forecasts.** QuickStats returned NASS's forecast for the coming season (year 2027 production, issued October 2026) even with `year__LE=2026`. The fetch drops rows after the last season and prints the drop.
- **Several rows share a statistic.** Production comes in boxes, tons and dollars, and by utilization (`UTILIZED`, `FRESH MARKET`, `PROCESSING`); yield and price for Florida oranges also appear in other units (gallons per box; `ON TREE EQUIV`, `FOB`). Always filter `unit_desc`, `util_practice_desc`, `class_desc`, `domain_desc` and `reference_period_desc` (price is for the `MARKETING YEAR`, the others for `YEAR`).
- **Check a yield against its parts.** QuickStats can contain a value that conflicts with NASS's own production and acreage (California oranges 2022 yield: 58, against about 285 implied). Compare yield with utilized boxes divided by bearing acres.
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
- **A station record has no county.** `/stations/GHCND:<id>` returns name, coordinates and registered dates only. Find the county by listing `/stations?locationid=FIPS:<county>` for each Florida county (`/locations/FIPS:<county>` gives its name); `fetch_county_data.py` does this. Retired codes (old Dade, `FIPS:12025`) return an empty record, and Miami-Dade is `FIPS:12086`.
- **Station names mislead:** Moore Haven Lock 1 is listed under Glades County, not Hendry; Tampa International under Hillsborough; Orlando Executive under Orange; Punta Gorda Airport under Charlotte.
- **IDs are easy to mix up:** `USW00012834` is Daytona Beach International, not Lakeland.
- **Co-op (`USC`) stations contain isolated sensor errors** (e.g. a 115 F daily high, 101 F daily lows). Both fetchers apply the plausibility filter described in `docs/METHODOLOGY.md`.
- **Requests fail loudly.** All fetchers share one client (`get_json`, in `fetch_data.py`) that retries three times, then stops and writes nothing; none has a substitute-data fallback. A year with no observations at a station is legitimate (stations start and stop): it is reported and left blank, not an error. A county station with data in fewer than 20 years is treated as a wrong station id and stops the run.
- **Published data can change.** NOAA backfilled 27 missing days of February 2018 at one station between two fetches a month apart, with no existing values altered. Treat a fetch as a snapshot of its date.

## Stations used

Catalog date ranges are not actual coverage. For observed coverage by year, see `data/station_coverage_matrix.csv` and the table in [METHODOLOGY.md](METHODOLOGY.md#counties-and-stations). Counties are from NOAA's station metadata (`data/stations.csv`).

| Station | ID | County (NOAA) | Used for |
|---|---|---|---|
| Lakeland 2 | USC00084802 | Polk | Polk panel |
| Moore Haven Lock 1 | USC00085895 | Glades | Hendry panel (nearest usable station; see METHODOLOGY) |
| Arcadia | USC00080228 | DeSoto | DeSoto panel |
| Archbold Biological Station | USC00080236 | Highlands | Highlands panel |

Probed but not used (coverage in `data/station_coverage_matrix.csv`): Tampa International (`USW00012842`), Orlando Executive (`USW00012841`), Lakeland Linder (`USW00012883`), Sebring (`USW00092827`), La Belle (`USC00084662`), Punta Gorda Airport (`USW00012812`), Avon Park 2 W (`USC00080369`), Bartow 1 SE (`USC00080478`), Lake Alfred (`USC00084707`), Mountain Lake (`USC00085973`), Winter Haven (`USC00089707`) and Gilbert Airport (`USW00012876`), Big Cypress (`USC00080737`), Clewiston (`USC00081654`) and Clewiston No. 2 (`USC00081651`), Devils Garden (`USC00082298`).

## Another source: FAWN

The University of Florida's Florida Automated Weather Network (FAWN) publishes open daily-summary CSVs by year (1997 onward) and by station at `https://fawn.ifas.ufl.edu/data/fawnpub/daily_summaries/`, with stations in growing areas (for example Lake Alfred, Frostproof, Arcadia, Sebring, Clewiston). It was assessed on 2026-10-20 and not used: it starts in 1997, years are not complete for many stations (Lake Alfred has a complete bloom window in 21 of 28 years, Arcadia 16, Clewiston 14), and the files have several header formats, split-year files, sentinel values such as -6999, and implausible readings (-63 C). Temperatures are in C and rain in inches. It could be added later for the county panels.
