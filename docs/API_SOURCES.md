# API Sources & Query Examples

Complete reference for USDA NASS and NOAA CDO APIs.

## 1. USDA NASS QuickStats API

### Overview
- **Service**: USDA National Agricultural Statistics Service (NASS)
- **Dataset**: QuickStats (crop data)
- **API**: RESTful HTTP
- **Rate Limit**: ~50 requests/sec
- **Authentication**: API Key (free registration)

### Registration
1. Visit: https://quickstats.nass.usda.gov/api/
2. Click "Get API Key"
3. Complete form (email required)
4. Receive key instantly (example: `C239BF21-79EB-3B84-B273-9CE323601358`)

### Endpoint
```
https://quickstats.nass.usda.gov/api/get
```

### Query Parameters

#### Required
| Parameter | Values | Example |
|-----------|--------|---------|
| `key` | Your API key | `key=YOUR_KEY` |
| `commodity_desc` | Crop name | `commodity_desc=CITRUS` |
| `agg_level_desc` | Aggregation level | `agg_level_desc=COUNTY` |
| `format` | JSON or CSV | `format=json` |

#### Filtering (Optional)
| Parameter | Values | Example |
|-----------|--------|---------|
| `state_alpha` | State code | `state_alpha=FL` |
| `county_name` | County name | `county_name=Polk County` |
| `year_GE` | Year ≥ | `year_GE=1990` |
| `year_LE` | Year ≤ | `year_LE=2024` |
| `statisticcat_desc` | Statistic | `statisticcat_desc=YIELD` |
| `unit_desc` | Unit | `unit_desc=LB / ACRE` |

### Example Query

#### Florida Citrus Yield (Polk County, 1990–2024)
```bash
curl "https://quickstats.nass.usda.gov/api/get?key=YOUR_KEY&commodity_desc=CITRUS&state_alpha=FL&county_name=Polk%20County&year_GE=1990&year_LE=2024&statisticcat_desc=YIELD&unit_desc=LB%20/%20ACRE&agg_level_desc=COUNTY&format=json"
```

#### Python Implementation
```python
import requests

NASS_URL = "https://quickstats.nass.usda.gov/api/get"
NASS_KEY = "YOUR_API_KEY"

params = {
    "key": NASS_KEY,
    "commodity_desc": "CITRUS",
    "state_alpha": "FL",
    "county_name": "Polk County",
    "year_GE": "1990",
    "year_LE": "2024",
    "statisticcat_desc": "YIELD",
    "unit_desc": "LB / ACRE",
    "agg_level_desc": "COUNTY",
    "format": "json"
}

response = requests.get(NASS_URL, params=params, timeout=30)
data = response.json()

# Extract yields
for row in data['data']:
    year = row['year']
    value = row['Value']  # lbs/acre
    print(f"{year}: {value}")
```

### Response Format
```json
{
  "data": [
    {
      "year": 1990,
      "county_name": "Polk County",
      "state_alpha": "FL",
      "commodity_desc": "CITRUS",
      "unit_desc": "LB / ACRE",
      "Value": "45993.43"
    },
    ...
  ]
}
```

### Data Quality
- **Suppressed values**: Marked as "D" (for confidentiality). Filter these out.
- **Missing years**: Some years may be omitted. Verify coverage.
- **Varieties**: "CITRUS" aggregates oranges, lemons, limes, grapefruit, tangerines.

### Multi-County Query
To fetch all major citrus counties (Orange, Polk, Citrus, Lake, DeSoto, Highlands, Hendry):

```python
counties = ["Orange County", "Polk County", "Citrus County", "Lake County", 
            "DeSoto County", "Highlands County", "Hendry County"]

all_data = []
for county in counties:
    params["county_name"] = county
    response = requests.get(NASS_URL, params=params)
    data = response.json()
    all_data.extend(data['data'])
```

---

## 2. NOAA Climate Data Online (CDO) API v1

### Overview
- **Service**: NOAA National Centers for Environmental Information (NCEI)
- **Dataset**: Global Summary of the Day (weather observations)
- **API**: RESTful HTTP (JSON response)
- **Rate Limit**: ~50 requests/sec per IP
- **Authentication**: API Token (free registration)

### Registration
1. Visit: https://www.ncei.noaa.gov/cdo-web/token/
2. Request token (instant email)
3. Token example: `ytMyljSmGhKmcJeNITGlrpqFZBHopvJP`

### Endpoint (v1)
```
https://www.ncei.noaa.gov/access/services/data/v1
```

### Query Parameters

#### Required
| Parameter | Values | Example |
|-----------|--------|---------|
| `dataset` | Dataset code | `dataset=global-summary-of-the-day` |
| `stations` | Station ID | `stations=USW00012834` |
| `startDate` | ISO 8601 | `startDate=1990-01-01` |
| `endDate` | ISO 8601 | `endDate=2024-12-31` |
| `dataTypes` | Data type codes | `dataTypes=TMAX,TMIN,PRCP` |
| `units` | "standard" or "metric" | `units=standard` |
| `format` | "json" or "csv" | `format=json` |
| `token` | Your API token | `token=YOUR_TOKEN` |

#### Optional
| Parameter | Values | Notes |
|-----------|--------|-------|
| `limit` | 1–1,000,000 | Default: 25. Increase for large datasets. |
| `offset` | Integer | Pagination (if results > limit) |

### Florida Weather Stations

#### Major Stations (Citrus Region)
| Station | Code | Location | Elevation |
|---------|------|----------|-----------|
| Lakeland Linder Regional | USW00012834 | Lakeland, FL | 155 ft |
| Tampa International Airport | USW00012842 | Tampa, FL | 26 ft |
| Orlando International Airport | USW00013880 | Orlando, FL | 95 ft |
| Sebring Airport | USW00014907 | Sebring, FL | 28 ft |

#### Finding Stations
```bash
# Search for stations near a city
curl "https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-summary-of-the-day&locationId=CITY:FL000011&limit=100&token=YOUR_TOKEN"
```

### Data Types
| Code | Description | Units |
|------|-------------|-------|
| `TMAX` | Maximum daily temperature | °F × 10 (e.g., 859 = 85.9°F) |
| `TMIN` | Minimum daily temperature | °F × 10 (e.g., 638 = 63.8°F) |
| `PRCP` | Precipitation | mm × 10 (e.g., 60 = 6.0 mm) |
| `TOBS` | Temperature at observation | °F × 10 |
| `TAVG` | Average daily temperature | °F × 10 |
| `DWPT` | Dew point | °F × 10 |
| `RHUM` | Relative humidity | % |
| `WDIR` | Wind direction | Degrees |
| `WSPD` | Wind speed | m/s × 10 |

### Example Query

#### Lakeland Weather (1990–2024)
```bash
curl "https://www.ncei.noaa.gov/access/services/data/v1?dataset=global-summary-of-the-day&stations=USW00012834&startDate=1990-01-01&endDate=2024-12-31&dataTypes=TMAX,TMIN,PRCP&units=standard&format=json&limit=50000&token=YOUR_TOKEN"
```

#### Python Implementation
```python
import requests

NOAA_URL = "https://www.ncei.noaa.gov/access/services/data/v1"
NOAA_TOKEN = "YOUR_API_TOKEN"

params = {
    "dataset": "global-summary-of-the-day",
    "stations": "USW00012834",  # Lakeland Linder
    "startDate": "1990-01-01",
    "endDate": "2024-12-31",
    "dataTypes": "TMAX,TMIN,PRCP",
    "units": "standard",
    "format": "json",
    "limit": 50000,
    "token": NOAA_TOKEN
}

response = requests.get(NOAA_URL, params=params, timeout=60)
data = response.json()

# Extract weather data
for row in data['results']:
    date = row['date']
    datatype = row['datatype']
    value = row['value']
    print(f"{date} {datatype}: {value}")
```

### Response Format
```json
{
  "results": [
    {
      "date": "1990-01-01",
      "datatype": "TMAX",
      "station": "USW00012834",
      "attributes": ",,W,",
      "value": 859
    },
    {
      "date": "1990-01-01",
      "datatype": "TMIN",
      "station": "USW00012834",
      "attributes": ",,W,",
      "value": 638
    },
    {
      "date": "1990-01-01",
      "datatype": "PRCP",
      "station": "USW00012834",
      "attributes": ",,W,",
      "value": 6
    }
  ]
}
```

### Data Quality
- **Missing values**: `null` in JSON response
- **Quality flags**: "attributes" field indicates data quality ("W" = manual verification)
- **Encoding**: All values are integers (decode by dividing by 10 or as-is for precipitation)

### Multi-Station Query
```python
stations = ["USW00012834", "USW00012842", "USW00013880", "USW00014907"]

all_weather = []
for station in stations:
    params["stations"] = station
    response = requests.get(NOAA_URL, params=params, timeout=60)
    data = response.json()
    all_weather.extend(data['results'])
    time.sleep(1)  # Respect rate limits
```

---

## 3. Rate Limiting & Backoff Strategy

### NASS API
- **Limit**: 50 req/sec
- **Backoff**: If 429 response, wait 1 min then retry
- **Best Practice**: Batch queries by county (1 request per county per year range)

### NOAA API
- **Limit**: 50 req/sec per IP
- **Backoff**: If 429 response, wait 2 min then retry
- **Best Practice**: Fetch all stations sequentially with 1 sec delay between requests

### Example Robust Implementation
```python
import requests
import time

def retry_get(url, params, max_retries=3, backoff_factor=2):
    """Robust GET with exponential backoff."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 429:
                wait_time = backoff_factor ** attempt
                print(f"Rate limited. Waiting {wait_time}s...")
                time.sleep(wait_time)
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(backoff_factor ** attempt)
            else:
                raise
```

---

## 4. Data Validation Checklist

### NASS Data
- [ ] All years 1990–2024 present
- [ ] No "D" (suppressed) values
- [ ] Yields in realistic range (10,000–50,000 lbs/acre)
- [ ] One record per year per county
- [ ] Data source labeled "NASS"

### NOAA Data
- [ ] All stations have coverage
- [ ] Data types: TMAX, TMIN, PRCP
- [ ] Temperature values decoded correctly
- [ ] Precipitation values reasonable
- [ ] No excessive gaps (>30 consecutive days)
- [ ] Data quality flags checked (W = verified)

---

## 5. References

- **USDA NASS QuickStats**: https://quickstats.nass.usda.gov/api/
- **NOAA CDO v1 API**: https://www.ncei.noaa.gov/cdo-web/webservices/v2/
- **Global Summary of the Day**: https://www.ncei.noaa.gov/products/global-summary-of-the-day
- **Station Search**: https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-day

