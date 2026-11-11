"""
Fetch the US consumer price index (CPI-U, all items, US city average, not seasonally adjusted;
BLS series CUUR0000SA0) monthly from the Bureau of Labor Statistics, to put the dollar values of
the citrus data in constant dollars.

Output: data/cpi_u_monthly.csv (year, month, cpi, note), October 1989 to the latest published month,
so that every citrus season from 1990 (October 1989 to September 1990) has its twelve months. A month
BLS did not publish (October 2025, because of the lapse in appropriations) stays in the file with a
blank cpi and BLS's own reason in note; nothing is estimated.

The BLS public API needs no key; its unregistered version returns at most 10 years per request and
allows 25 requests a day, so the range is fetched in four windows. A failed request, a response that
says it was not processed, or a window with no data stops the run and writes nothing.
"""

import sys
import time

import pandas as pd
import requests

try:                                   # python src/fetch_cpi.py (src/ is on the path)
    import manifest
    from fetch_industry_data import FetchError
except ImportError:                    # imported as a package
    from src import manifest
    from src.fetch_industry_data import FetchError

SERIES_ID = "CUUR0000SA0"
URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"    # POST; the GET form ignores the year range
WINDOWS = [(1989, 1998), (1999, 2008), (2009, 2018), (2019, 2028)]
FIRST_MONTH = (1989, 10)
OUTPUT = "data/cpi_u_monthly.csv"


def post_json(url, body, attempts=3):
    """POST JSON and parse the reply, retrying transient failures; FetchError if all attempts fail."""
    reason = "unknown error"
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, json=body, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            reason = f"HTTP {e.response.status_code}"
        except (requests.RequestException, ValueError) as e:
            reason = type(e).__name__
        if attempt < attempts:
            time.sleep(2 ** attempt)
    raise FetchError(f"{url} failed after {attempts} attempts ({reason})")


def parse_window(payload, label):
    """Monthly rows (year, month, cpi) from one BLS response; FetchError if BLS did not return data."""
    if payload.get("status") != "REQUEST_SUCCEEDED":
        raise FetchError(f"BLS {label}: {payload.get('status')} {payload.get('message', [])[:1]}")
    try:
        points = payload["Results"]["series"][0]["data"]
    except (KeyError, IndexError):
        raise FetchError(f"BLS {label}: no series in the response")
    rows = []
    for p in points:
        period = str(p.get("period", ""))
        if not (period.startswith("M") and period != "M13"):      # M13 is the annual average
            continue
        value = str(p.get("value", "")).strip()
        year, month = int(p["year"]), int(period[1:])
        if value in ("", "-"):                                    # a month BLS did not publish: kept blank, with its reason
            reason = "; ".join(f.get("text", "") for f in p.get("footnotes", []) if f.get("text"))
            rows.append({"year": year, "month": month, "cpi": float("nan"), "note": reason or "not published"})
            continue
        try:
            rows.append({"year": year, "month": month, "cpi": float(value), "note": ""})
        except ValueError:
            raise FetchError(f"BLS {label}: unexpected value {value!r}")
    if not any(r["cpi"] == r["cpi"] for r in rows):               # NaN != NaN: no published month at all
        raise FetchError(f"BLS {label}: the response has no monthly values")
    return rows


def build_cpi():
    rows = []
    for start, end in WINDOWS:
        label = f"{start}-{end}"
        body = {"seriesid": [SERIES_ID], "startyear": str(start), "endyear": str(end)}
        rows += parse_window(post_json(URL, body), label)
        print(f"  [OK] CPI-U {label}: {len(rows)} months so far")
    df = (pd.DataFrame(rows).drop_duplicates(["year", "month"]).sort_values(["year", "month"]).reset_index(drop=True))
    df = df[(df["year"] > FIRST_MONTH[0]) | ((df["year"] == FIRST_MONTH[0]) & (df["month"] >= FIRST_MONTH[1]))]
    months = df["year"] * 12 + df["month"] - 1
    if (months.diff().dropna() != 1).any():
        raise FetchError("CPI-U rows are not consecutive months; the response is missing a month inside the range")
    return df.reset_index(drop=True)


def main():
    print("=" * 60 + "\nCPI-U, ALL ITEMS, US CITY AVERAGE (BLS, %s)\n" % SERIES_ID + "=" * 60)
    try:
        df = build_cpi()
    except FetchError as e:
        print(f"\n[FAILED] {e}\nNothing was written; the existing file is unchanged.")
        sys.exit(1)
    df.to_csv(OUTPUT, index=False)
    manifest.record(OUTPUT, f"US Bureau of Labor Statistics, CPI-U all items, series {SERIES_ID}", len(df))
    first, last = df.iloc[0], df.iloc[-1]
    print(f"\n[OK] Saved {OUTPUT} ({len(df)} months, {int(first.year)}-{int(first.month):02d} to "
          f"{int(last.year)}-{int(last.month):02d}; latest CPI {last.cpi})")
    for r in df[df["cpi"].isna()].itertuples():
        print(f"  [NOTE] {r.year}-{r.month:02d} not published: {r.note}")


if __name__ == "__main__":
    main()
