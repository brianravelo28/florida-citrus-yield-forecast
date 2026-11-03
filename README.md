# Florida Orange Yield, Acreage and Winter Frost

![Dashboard overview: the yield headline and statewide yield chart](docs/screenshot.jpg)

A dashboard of Florida orange yield, county acreage and winter frost by weather station, built from public data from the USDA's National Agricultural Statistics Service (NASS) and NOAA (the National Oceanic and Atmospheric Administration). It asks one question: **what happened to Florida's orange yield and acreage, and does winter frost explain it?** It is for anyone following the decline of Florida's orange industry, including analysts and students.

**Live dashboard:** <https://florida-orange-yield-dashboard.onrender.com/> (free tier: the first load after idle can take about 40 seconds)

## What the data shows

- **Florida's orange yield fell 87% from its 2004 peak (38,520 lb/acre) to its 2023 low (5,130), and has recovered only partly.** 2024 was 7,020, 2025 was 6,570, and 2026 is a preliminary 9,180, still 76% below the peak. The 87% is measured from the 2004 peak.
- **Bearing orange acreage fell 37% to 47% in every county with published Census totals:** Polk -46.5% (2002-2022), DeSoto -37.3% (2002-2022), Hendry -44.7% (2012-2022), Highlands -46.3% (2002-2017). The periods differ because USDA withheld some totals.
- **Winter frost did not rise at the four stations measured.** Bloom-season frost days (January-March nights at or below 32 F) trend between about -0.5 and +0.5 days per decade at each station. Frost varies far more between stations (a mean of 1.0 to 6.5 days a year) than over time, and the cold winter of 2010 is the worst at the three stations with a complete record for it.

Frost is shown next to the yield decline but is not tested as a cause. Citrus greening disease (HLB) and hurricane damage are not analyzed here.

## What the dashboard shows

1. **Overview:** the headline, peak, low and latest yield, and the statewide yield chart. The newest season is drawn as a hollow, dashed point because NASS publishes it as a preliminary estimate.
2. **Frost Map:** a map of the four weather stations. Marker color and size show mean bloom-season frost days, and hovering shows the station, its county, the winters counted and the trend.
3. **County Comparison:** frost by station over time, Census bearing acreage by county, and a year-by-year panel (frost, summer heat and growing degree days, a measure of accumulated heat).

## Data

| Dataset | Source | Details |
|---|---|---|
| Statewide orange yield | USDA NASS QuickStats | 1990-2026, 37 seasons, converted to lb/acre at 90 lb per box. NASS labels a season by its end year (2023 is the 2022-23 season). 2026 is preliminary. |
| County bearing acreage | USDA Census of Agriculture | Oranges, all varieties, 2002, 2007, 2012, 2017, 2022. Polk, Hendry, DeSoto and Highlands: 20 county-years, 16 published and 4 withheld by USDA (left blank). Plus every Florida county, to check the county choice. |
| Weather | NOAA daily records (GHCND, the Global Historical Climatology Network daily dataset) | Daily highs, lows and rainfall, 1990-2026, from one station per county (below). |
| Station locations | NOAA station metadata | Coordinates and county as NOAA lists them. |

The weather stations: **Polk** (Lakeland 2), **Hendry** (Moore Haven Lock 1, which NOAA lists in neighboring Glades County), **DeSoto** (Arcadia) and **Highlands** (Archbold Biological Station). All data are real observations; none is synthetic. All files were pulled on 2026-11-03. Why these stations and counties is in [docs/METHODOLOGY.md](docs/METHODOLOGY.md).

## Missing and withheld data

Nothing is estimated or filled in. USDA withheld four county acreage totals (Hendry 2002 and 2007, DeSoto 2012, Highlands 2022); they appear as gaps. Frost is counted for a winter only if every January-March night was observed, so stations have different numbers of counted winters (24 to 37 of 37), and the chart legend and map hover show the count. Blanks appear as gaps or as *missing*, never as zero.

## Run it

```bash
git clone https://github.com/brianravelo28/florida-orange-yield-dashboard.git
cd florida-orange-yield-dashboard
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_dashboard.py          # http://127.0.0.1:8050  (run from the repo root)
```

Requires Python 3.12 or newer (the pinned numpy needs it); `requirements.txt` is pinned to the versions the live site runs on (Python 3.14), and CI tests Python 3.13 and 3.14. The data files are committed, so the dashboard runs right away. To rebuild them, get free keys from [USDA NASS](https://quickstats.nass.usda.gov/api) and [NOAA](https://www.ncei.noaa.gov/cdo-web/token) and set them as environment variables (the scripts stop with a clear message if a key is unset, and no key is stored in the code):

```bash
export NASS_KEY=your-nass-key           # PowerShell: $env:NASS_KEY = "your-nass-key"
export NOAA_API_KEY=your-noaa-token

python src/fetch_data.py                 # statewide yield
python src/fetch_county_data.py          # county acreage, station weather and locations (about 10 minutes)
python src/county_feature_engineering.py # -> data/county_features.csv and the frost summary
python src/fetch_county_ranking.py       # optional: every county's Census acreage
python src/station_coverage.py           # optional: re-probe station coverage (about 15 minutes)
```

A failed API call stops a script and writes nothing.

## Known limitations

- **Stations, not counties.** Each weather series is one station. Archbold is a notably cold site (open scrub), so its frost counts are not representative of nearby groves, and Moore Haven Lock 1 sits in Glades County, not Hendry. Read frost differences as differences between stations.
- **Station records have gaps.** Polk's station starts in late 1995, DeSoto's ends in April 2021, and Hendry's frost record ends in 2020. Polk's 2010 winter, the coldest at the other stations, is incomplete.
- **Yield is statewide only.** QuickStats has no county orange yield. NASS's Citrus Summary lists county production, but as an apportionment of the statewide harvest, so no county yield is shown or estimated.
- **The 2026 yield is preliminary** and NASS revises it a year later.
- **Four counties, not all.** They are the four largest by bearing orange acres in the 2017 Census. Hardee, fifth in 2017 and fourth in 2022, is not included; its weather stations were not assessed.
- **Frost is not drawn on the yield chart,** because frost years are calendar years and NASS seasons are labeled by their end year.
- **Weather is not the only possible explanation.** The data cannot separate frost from disease, hurricanes or land use.

## Tests

`pytest` runs small checks on the frost counting, the missing-data rules (blank, never zero), growing degree days, rolling rainfall windows, the frost summary, and the committed data (withheld acreage stays blank, the latest yield season is marked preliminary, the county choice matches the Census ranking). CI runs them on every push.

## Project structure

```
src/        fetch_data, fetch_county_data, fetch_county_ranking, feature_engineering,
            county_feature_engineering, station_coverage, app (Dash dashboard)
tests/      feature-engineering and data tests
data/       yield, county acreage, station weather and locations, frost summary
docs/       METHODOLOGY, SCHEMA, API_SOURCES, citations
```

Deployed on [Render](https://render.com) from `main` (see [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md)); the app reads the committed files, so no API keys are needed at runtime.

## License

MIT, see [LICENSE](LICENSE). Data: USDA NASS QuickStats, USDA Census of Agriculture, NOAA NCEI Global Historical Climatology Network (daily).
