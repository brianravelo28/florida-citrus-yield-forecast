# Data Schema

Three CSVs in `data/`, pulled on 2026-11-10.

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

Series coverage: oranges and grapefruit in Florida, California and Texas (1990-2026) and Arizona (to 2012 and 2009); tangerines in Florida and California (1990-2026) and Arizona (to 2015); lemons in California and Arizona (1990-2026) and Florida (2025-2026 only); tangelos in Florida (to 2016).

### `data/citrus_totals_by_state.csv` - 152 rows (2008-2026)

NASS's own state totals across all citrus (QuickStats commodity `CITRUS TOTALS`), from `src/fetch_industry_data.py`. One row per state, year and measure; NASS publishes no totals before 2008. The totals include values that NASS withholds at the fruit level, so they cover years in which the fruit rows are blank (see [METHODOLOGY.md](METHODOLOGY.md#totals-and-gaps)).

| Column | Description |
|---|---|
| `state` | `FL`, `CA`, `TX`, `AZ` |
| `year` | NASS season, labeled by its end year |
| `measure` | `bearing_acres` (acres) or `value_of_production_usd` (nominal dollars, packinghouse-door equivalent), defined as in the fruit file |
| `value` | The published total; every one of the 152 is present |
| `note` | Empty (no value is withheld or unavailable) |
| `status` | `reported`, or `preliminary` for the season ending in 2026 |

### `data/cpi_u_monthly.csv` - 445 rows (October 1989 to October 2026)

The US consumer price index, from the Bureau of Labor Statistics (CPI-U, all items, US city average, not seasonally adjusted; series `CUUR0000SA0`), written by `src/fetch_cpi.py`. Used to express dollar values in constant 2025 dollars (see [METHODOLOGY.md](METHODOLOGY.md#constant-dollars-shares-and-units)).

| Column | Description |
|---|---|
| `year`, `month` | Calendar month of the index |
| `cpi` | Index level (1982-84 = 100). **Blank for October 2025**, which BLS did not publish |
| `note` | Empty, or BLS's reason for the blank ("Data unavailable due to the 2025 lapse in appropriations") |

Blank values in the fruit file: 63 of 2,483 (48 withheld, 15 not available). A value is never estimated. One published value is flagged by the dashboard but not changed: `yield_boxes_per_acre` for California oranges in 2022 (58), which conflicts with NASS's own production and acreage (see [METHODOLOGY.md](METHODOLOGY.md#checks-on-the-data)).
