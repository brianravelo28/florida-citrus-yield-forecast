# API Sources and Notes

How this project queries USDA NASS and NOAA, plus the non-obvious behaviors that cost time to discover. API keys are free; set them as the `NASS_KEY` / `NOAA_TOKEN` constants at the top of `src/fetch_data.py` and `src/fetch_county_data.py`.

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
- **County names follow NASS spelling:** DeSoto County is `DE SOTO`; `DESOTO` returns HTTP 400.
- **An invalid parameter combination returns HTTP 400** (`bad request - invalid query`) without saying which parameter is wrong. Narrow the query to find it.

## NOAA CDO v2

Docs: <https://www.ncei.noaa.gov/cdo-web/webservices/v2>

```
GET https://www.ncei.noaa.gov/cdo-web/api/v2/data        (header: token: <NOAA_TOKEN>)
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
- **The station catalog is not evidence of data.** In our tests `/datatypes` ignored the `datatypeid` filter and returned a truncated list, and registered date ranges did not guarantee observations exist. Bartow Municipal (`USW00012809`) is registered from 1955 but returned no observations in any year tested (1990-2024). Confirm a station by requesting actual observations across several years inside its registered range.
- **IDs are easy to mix up:** `USW00012834` is Daytona Beach International, not Lakeland.
- **Co-op (`USC`) stations contain isolated sensor errors** (e.g. a 115 F daily high, 101 F daily lows). Both fetchers apply the plausibility filter described in `docs/METHODOLOGY.md`.
- **Requests fail loudly.** `fetch_data.py` retries three times, then stops and writes nothing; it has no substitute-data fallback.

## Stations used

Catalog date ranges shown for reference; actual coverage has gaps (see `docs/METHODOLOGY.md`).

| Station | ID | Used for | Catalog range |
|---|---|---|---|
| Lakeland Linder | USW00012883 | Statewide model, Polk | 1948- |
| Tampa International | USW00012842 | Statewide model, Polk | 1939- |
| Orlando Executive | USW00012841 | Statewide model, Polk | 1892- |
| Sebring | USW00092827 | Statewide model, Polk, Highlands | 2007-12- |
| La Belle | USC00084662 | Hendry | 1929-2019-05 |
| Moore Haven Lock 1 | USC00085895 | Hendry | 1918- |
| Arcadia | USC00080228 | DeSoto | 1899-2021-04 |
| Punta Gorda Airport | USW00012812 | DeSoto | 1996-10- |
| Avon Park 2 W | USC00080369 | Highlands | 1892-2022-04 |

Not used: Bartow Municipal (no observations, above). Clewiston (`USC00081654`) returns real TMAX/TMIN/PRCP for 1990-2003 (sparse in some years) and could strengthen Hendry's early record, but is not currently included.
