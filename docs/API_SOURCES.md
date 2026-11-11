# API Sources and Notes

How this project queries USDA NASS QuickStats, plus the non-obvious behaviors that cost time to discover. The API key is free; export it as the `NASS_KEY` environment variable. The fetch script reads it at run time and stops with a clear message if it is unset; no key is stored in the code.

## BLS consumer price index

Docs: <https://www.bls.gov/developers/>

Price index query (`src/fetch_cpi.py`), four 10-year windows:

```
POST https://api.bls.gov/publicAPI/v1/timeseries/data/
  {"seriesid": ["CUUR0000SA0"], "startyear": "1989", "endyear": "1998"}
```

- **No key is needed** for the unregistered version, which returns at most 10 years per request and allows 25 requests a day.
- **Use POST.** The GET form (`.../data/CUUR0000SA0?startyear=...`) returned only the latest 33 months whatever year range was sent.
- **HTTP 200 does not mean success.** The body carries `status`; anything other than `REQUEST_SUCCEEDED` stops the run.
- **A month can be unpublished.** October 2025 comes back with value `-` and a footnote (code `X`, "Data unavailable due to the 2025 lapse in appropriations"). The fetch keeps it as a blank row with that note.
- **`M13` is the annual average**, not a month; the fetch skips it.
- **Terms.** BLS content is in the public domain and BLS asks that it is cited as the source ([copyright page](https://www.bls.gov/opub/copyright-information.htm)). Its API [terms of service](https://www.bls.gov/developers/termsOfService.htm) ask users of the API to cite the date the data were retrieved and to state that "BLS.gov cannot vouch for the data or analyses derived from these data after the data have been retrieved from BLS.gov"; the dashboard's source notice does both, with the date read from `data/manifest.json`. The BLS logo is not used.

## USDA NASS QuickStats

Docs: <https://quickstats.nass.usda.gov/api>

Terms: using the API means accepting the NASS API Terms of Service (on that page), which ask that any service using the API "display the following notice prominently within the application": "This product uses the NASS API but is not endorsed or certified by NASS." The dashboard shows it in its header, with the pull date read from `data/manifest.json`.

Citrus by state query (`src/fetch_industry_data.py`), one request per fruit and measure:

```
GET https://quickstats.nass.usda.gov/api/api_GET/
  key=<NASS_KEY>  commodity_desc=<ORANGES|GRAPEFRUIT|TANGERINES|LEMONS|TANGELOS>  agg_level_desc=STATE
  source_desc=SURVEY  statisticcat_desc=<AREA BEARING|YIELD|PRODUCTION|PRICE RECEIVED>  unit_desc=<see below>
  year__GE=1990  year__LE=2026  format=json
```

Units used: `ACRES`, `BOXES / ACRE`, `BOXES` and `TONS` (production, utilization `UTILIZED`), `$, PHD EQUIV` (value), `$ / BOX, PHD EQUIV` (price, reference period `MARKETING YEAR`). The script then keeps `class_desc=ALL CLASSES` and `domain_desc=TOTAL` rows.

Things to know:

- **The path is `/api/api_GET/`.** `/api/get` returns 404.
- **Operators use double underscores:** `year__GE`, `year__LE`.
- **Commodity names must match exactly.** There is no plain `CITRUS`; use `ORANGES`, `GRAPEFRUIT`, `TANGERINES`, `LEMONS`, `TANGELOS` or `CITRUS TOTALS`. List valid values with `/api/get_param_values/?key=...&param=commodity_desc`.
- **`CITRUS TOTALS` is a state total across all citrus, from 2008.** The same query with `commodity_desc=CITRUS TOTALS` returns bearing acres and value of production for each state (`unit_desc` `ACRES` and `$, PHD EQUIV`; class `ALL CLASSES`, domain `TOTAL`), 2008 to the preliminary season. The value totals include fruit values that are withheld `(D)` in the fruit-level rows, so they cover 2009-2016 where the fruit rows are blank.
- **The value field is `Value` (capital V).** Reading lowercase `value` silently yields nothing. Suppression codes such as `(D)` can arrive padded with whitespace.
- **`(D)` means withheld**, not zero or missing: NASS withholds the value to avoid disclosing individual operations' data.
- **QuickStats has yield and production only at state level** for citrus. County-level rows cover Census area statistics only; querying `PRODUCTION` or `YIELD` at county level returns HTTP 400. NASS's separate Citrus Summary publication lists county production, but states that it is an apportionment of the statewide harvest, not a county measurement.
- **The newest season is preliminary.** NASS loads the season ending in the current year (2026) as an August estimate and revises it a year later; `src/fetch_industry_data.py` marks it `status = preliminary`.
- **`year__LE` does not exclude forecasts.** QuickStats returned NASS's forecast for the coming season (year 2027 production, issued October 2026) even with `year__LE=2026`. The fetch drops rows after the last season and prints the drop.
- **Several rows share a statistic.** Production comes in boxes, tons and dollars, and by utilization (`UTILIZED`, `FRESH MARKET`, `PROCESSING`); yield and price for Florida oranges also appear in other units (gallons per box; `ON TREE EQUIV`, `FOB`). Always filter `unit_desc`, `util_practice_desc`, `class_desc`, `domain_desc` and `reference_period_desc` (price is for the `MARKETING YEAR`, the others for `YEAR`).
- **Check a yield against its parts.** QuickStats can contain a value that conflicts with NASS's own production and acreage (California oranges 2022 yield: 58, against about 285 implied). Compare yield with utilized boxes divided by bearing acres.
- **An invalid parameter combination returns HTTP 400** (`bad request - invalid query`) without saying which parameter is wrong. Narrow the query to find it.
- **The fetch fails loudly.** It retries three times, then stops and writes nothing; there is no substitute-data fallback.
