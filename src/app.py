"""
Plotly Dash app: the US citrus industry by fruit and state (acreage, yield,
price and value of production, 1990-2026), plus a Florida deep dive (winter
frost by weather station and county orange acreage). Descriptive only; no
model, no forecast.

Tabs: Industry Overview, By Fruit, By State, Florida: Frost Map, Florida: Counties.
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd

try:                                  # gunicorn src.app:server and run_dashboard.py import it as a package
    from src import citrus_data as cd
except ImportError:                   # python src/app.py
    import citrus_data as cd

# ---------------------------------------------------------------------------
# Data (all committed CSVs; see docs/SCHEMA.md)
# ---------------------------------------------------------------------------
citrus = cd.load_citrus("data/citrus_by_state.csv")
citrus_plot = cd.blank_conflicts(citrus)          # flagged yields drawn as gaps; the file is untouched
conflicts = cd.yield_conflicts(citrus)
county_features = pd.read_csv("data/county_features.csv")
stations = pd.read_csv("data/stations.csv")
frost_summary = pd.read_csv("data/station_frost_summary.csv")

LATEST_YEAR = int(citrus["year"].max())
LATEST_PRELIM = bool((citrus.loc[citrus["year"] == LATEST_YEAR, "status"] == "preliminary").all())
PRELIM_TAG = " (preliminary)" if LATEST_PRELIM else ""

STATE_COLORS = {"FL": "#fd7e14", "CA": "#0d6efd", "TX": "#198754", "AZ": "#6f42c1"}
FRUIT_COLORS = {"Oranges": "#fd7e14", "Grapefruit": "#e8537a", "Tangerines": "#f2b705",
                "Lemons": "#9ec31a", "Tangelos": "#8d6e63"}
COLORS = {'background': '#f8f9fa', 'text': '#212529', 'primary': '#0d6efd', 'success': '#198754',
          'warning': '#ffc107', 'danger': '#dc3545'}

NOMINAL_NOTE = ("Dollar values are nominal (not adjusted for inflation) and use NASS's packinghouse-door "
                "equivalent basis.")
PRELIM_NOTE = (f"{LATEST_YEAR} is NASS's preliminary estimate for the season ending that year and is revised a "
               "year later. Seasons are labeled by their end year (2023 is the 2022-23 season).")


def _state(code):
    return cd.STATE_NAMES.get(code, code)


# ---------------------------------------------------------------------------
# Industry summary, computed from the data (totals are blank in years with a missing part)
# ---------------------------------------------------------------------------
acres_total = cd.complete_total(citrus, "bearing_acres").dropna()
value_total = cd.complete_total(citrus, "value_of_production_usd").dropna()
acres_by_state = cd.complete_total(citrus, "bearing_acres", by="state")
value_by_state = cd.complete_total(citrus, "value_of_production_usd", by="state")

ACRES_PEAK_YEAR, ACRES_PEAK = int(acres_total.idxmax()), float(acres_total.max())
ACRES_LATEST = float(acres_total.loc[LATEST_YEAR])
ACRES_FALL = round(-cd.pct_change(ACRES_LATEST, ACRES_PEAK))

# Each state's share of the US value of production in the same year. Shares compare states with
# each other, so inflation cancels out (the dollar totals themselves are nominal).
value_share = value_by_state.div(value_by_state.sum(axis=1), axis=0) * 100
FIRST_VALUE_YEAR = 1990
SHARE_FL_FIRST, SHARE_FL_LAST = value_share.loc[FIRST_VALUE_YEAR, "FL"], value_share.loc[LATEST_YEAR, "FL"]
SHARE_CA_FIRST, SHARE_CA_LAST = value_share.loc[FIRST_VALUE_YEAR, "CA"], value_share.loc[LATEST_YEAR, "CA"]

HEADLINE = (
    f"US citrus bearing acreage fell {ACRES_FALL}% from its {ACRES_PEAK_YEAR} peak to {LATEST_YEAR}{PRELIM_TAG}, and the "
    f"industry moved west: Florida's share of the value of production fell from {SHARE_FL_FIRST:.0f}% in "
    f"{FIRST_VALUE_YEAR} to {SHARE_FL_LAST:.0f}% in {LATEST_YEAR}, while California's rose from "
    f"{SHARE_CA_FIRST:.0f}% to {SHARE_CA_LAST:.0f}%."
)

# ---------------------------------------------------------------------------
# Florida deep dive data
# ---------------------------------------------------------------------------
COUNTY_LIST = sorted(county_features["county_name"].unique().tolist())
COUNTY_YEARS = sorted(county_features["year"].unique().tolist())
COUNTY_COLORS = {"Polk": "#0d6efd", "Hendry": "#198754", "DeSoto": "#fd7e14", "Highlands": "#6f42c1"}
station_info = (stations.rename(columns={"panel_county": "county_name"})
                .merge(frost_summary, on="county_name", how="left").set_index("county_name"))

# Metrics shown in the Yearly Outlook panel. Years where a county's station was
# missing too many days are NA ("missing"), not zero. The panel opens on the
# latest year in which every county has all three metrics.
OUTLOOK_METRICS = ["frost_days_bloom", "tmax_mean_grow", "gdd_total_grow"]
_n_complete = county_features.groupby("year").apply(
    lambda g: int(g[OUTLOOK_METRICS].notna().all(axis=1).sum()), include_groups=False)
_complete_years = _n_complete[_n_complete == county_features["county_name"].nunique()]
DEFAULT_OUTLOOK_YEAR = int(_complete_years.index.max()) if len(_complete_years) else COUNTY_YEARS[-1]


def _station_phrase(county):
    row = station_info.loc[county]
    where = "" if row["county_noaa"] == county else f" (NOAA lists it in {row['county_noaa']} County)"
    return f"{county} - {row['station_label']}{where}"


STATION_NOTE = "Stations (one per county): " + "; ".join(_station_phrase(c) for c in COUNTY_LIST) + "."


def _join_years(years):
    years = [str(int(y)) for y in years]
    return years[0] if len(years) == 1 else ", ".join(years[:-1]) + " and " + years[-1]


# County-years where USDA withheld the Census acreage total. Shown as gaps in
# the chart and named in its footnote; never estimated.
_withheld = county_features[county_features["acreage_status"] == "withheld"]
WITHHELD_NOTE = "; ".join(f"{c} {_join_years(g['year'])}" for c, g in _withheld.groupby("county_name"))
ACREAGE_NOTE = (
    "Real USDA Census of Agriculture figures (published every 5 years); dotted lines only "
    "connect published points."
    + (" Gaps are totals USDA withheld (marked '(D)' in the Census, to avoid disclosing "
       f"individual operations' data): {WITHHELD_NOTE}. They are not estimated." if WITHHELD_NOTE else "")
)

app = dash.Dash(__name__)

KPI_STYLE = {'textAlign': 'center', 'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px',
             'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'margin': '10px'}
CARD_STYLE = {'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}
FOOTNOTE_STYLE = {'fontSize': '12px', 'color': '#888', 'marginTop': '10px'}


def create_kpi_card(label, value, unit="", color=COLORS['primary']):
    return html.Div([
        html.H4(label, style={'color': '#666', 'fontSize': '14px', 'marginBottom': '10px'}),
        html.H2(value if isinstance(value, str) else f"{value:,.0f}", style={'color': color, 'marginBottom': '5px'}),
        html.P(unit, style={'color': '#999', 'fontSize': '12px'})
    ], style=KPI_STYLE)


CHART_HINT_ZOOM = "Drag to zoom into part of the chart; double-click the chart to reset the view."
CHART_HINT_LEGEND = " Click a legend entry to hide that series; double-click it to isolate it."


def chart_hint(legend=True):
    text = CHART_HINT_ZOOM + (CHART_HINT_LEGEND if legend else "")
    return html.P(text, style={'margin': '4px 2px 0', 'color': '#888', 'fontSize': '13px', 'fontStyle': 'italic'})


# ---------------------------------------------------------------------------
# Chart builders for the industry tabs
# ---------------------------------------------------------------------------
def _shade_latest(fig):
    """Light band over the preliminary season."""
    if LATEST_PRELIM:
        fig.add_vrect(x0=LATEST_YEAR - 0.5, x1=LATEST_YEAR + 0.5, fillcolor="grey", opacity=0.15, line_width=0,
                      annotation_text="prelim.", annotation_position="top left", annotation_font_size=10)


def stacked_bars(total_by, title, ytitle, scale, colors, labels, hover_fmt):
    """Stacked yearly bars; a year whose parts are not all published is left empty, not shown partly."""
    fig = go.Figure()
    for col in total_by.columns:
        fig.add_trace(go.Bar(x=total_by.index, y=total_by[col] / scale, name=labels(col), marker_color=colors.get(col),
                             hovertemplate=f"<b>%{{x}}</b><br>{labels(col)}: %{{y:{hover_fmt}}}<extra></extra>"))
    fig.update_layout(barmode="stack", title=title, xaxis_title="Season (end year)", yaxis_title=ytitle,
                      height=430, template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", yanchor="top", y=-0.18))
    _shade_latest(fig)
    return fig


def gap_note(df, measure, scope_label):
    """Sentence naming the years in which a total is left empty because a part is missing."""
    years = cd.incomplete_years(df, measure)
    if not years:
        return ""
    return (f" {scope_label} is left empty in {cd.year_ranges(years)}: in those years NASS withheld or did not "
            "publish a value for at least one fruit and state, and a partial total would understate it.")


def build_acres_by_state():
    return stacked_bars(acres_by_state, "Bearing Acres of Citrus, by State", "Bearing acres (thousands)", 1e3,
                        STATE_COLORS, _state, ",.0f")


def build_value_by_fruit():
    by_fruit = cd.complete_total(citrus, "value_of_production_usd", by="fruit")
    by_fruit = by_fruit[[f for f in cd.FRUIT_ORDER if f in by_fruit.columns]]
    return stacked_bars(by_fruit, "Value of Production, by Fruit", "Value of production ($ million, nominal)", 1e6,
                        FRUIT_COLORS, lambda f: f, ",.0f")


def build_value_share_by_state():
    fig = stacked_bars(value_share, "Share of US Citrus Value of Production, by State", "Share of US value (%)", 1,
                       STATE_COLORS, _state, ".0f")
    fig.update_yaxes(range=[0, 100])
    return fig


# ---------------------------------------------------------------------------
# Florida deep-dive builders
# ---------------------------------------------------------------------------
def build_map_figure():
    """One marker per weather station, sized and colored by mean bloom-season frost days."""
    df = station_info.reset_index()
    hover = []
    for _, r in df.iterrows():
        hover.append(
            f"<b>{r['station_label']}</b><br>NOAA county: {r['county_noaa']}"
            f"<br>Used for the {r['county_name']} panel"
            f"<br>Winters counted: {int(r['years_counted'])} of {int(r['years_in_range'])} "
            f"({int(r['first_year_counted'])}-{int(r['last_year_counted'])})"
            f"<br>Mean frost days a year: {r['mean_frost_days']:.1f}"
            f"<br>Most: {int(r['max_frost_days'])} ({int(r['max_frost_year'])})"
            f"<br>Trend: {r['trend_days_per_decade']:+.1f} days per decade")
    fig = go.Figure(go.Scattermap(
        lat=df["latitude"], lon=df["longitude"], mode="markers+text",
        text=df["station_label"], textposition="top right",
        marker=dict(size=14 + df["mean_frost_days"] * 3, color=df["mean_frost_days"], colorscale="YlGnBu",
                    cmin=0, showscale=True, opacity=0.85, colorbar=dict(title="Mean frost<br>days a year")),
        hovertext=hover, hoverinfo="text"))
    fig.update_layout(
        map=dict(style="open-street-map",
                 center=dict(lat=float(df["latitude"].mean()), lon=float(df["longitude"].mean())), zoom=6.6),
        margin=dict(l=0, r=0, t=10, b=0), height=520)
    return fig


def build_station_table():
    df = station_info.reset_index()
    head = ["Station", "NOAA county", "Panel county", "Winters counted", "First-last counted",
            "Mean frost days", "Most (year)", "Trend per decade"]
    cell = {'padding': '6px 10px', 'borderBottom': '1px solid #eee', 'textAlign': 'left', 'fontSize': '13px'}
    rows = [html.Tr([html.Th(h, style={**cell, 'fontWeight': 'bold'}) for h in head])]
    for _, r in df.iterrows():
        vals = [r["station_label"], r["county_noaa"], r["county_name"],
                f"{int(r['years_counted'])} of {int(r['years_in_range'])}",
                f"{int(r['first_year_counted'])}-{int(r['last_year_counted'])}",
                f"{r['mean_frost_days']:.1f}", f"{int(r['max_frost_days'])} ({int(r['max_frost_year'])})",
                f"{r['trend_days_per_decade']:+.1f}"]
        rows.append(html.Tr([html.Td(v, style=cell) for v in vals]))
    return html.Table(rows, style={'borderCollapse': 'collapse', 'width': '100%'})


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
METRICS = {
    "bearing_acres": ("Bearing acres", ",.0f"),
    "yield_boxes_per_acre": ("Yield (boxes per acre)", ",.0f"),
    "yield_pct_of_peak": ("Yield, % of each state's own peak", ".0f"),
    "production_boxes": ("Utilized production (million boxes)", ",.1f"),
    "value_of_production_usd": ("Value of production ($ million, nominal)", ",.0f"),
    "price_usd_per_box": ("Price per box ($, packinghouse-door)", ",.2f"),
}
FRUITS = [f for f in cd.FRUIT_ORDER if f in set(citrus["fruit"])]
STATES = [s for s in cd.STATE_NAMES if s in set(citrus["state"])]

app.layout = html.Div([
    html.Div([
        html.H1("US Citrus Industry: Acreage, Yield and Value by State", style={
            'color': COLORS['primary'], 'marginBottom': '10px', 'fontSize': '32px', 'fontWeight': 'bold'}),
        html.P("How has the US citrus industry changed since 1990, and where did it go?",
               style={'color': '#333', 'margin': '0 0 6px', 'fontSize': '16px'}),
        html.P("For anyone following US agriculture, including analysts and students. Real USDA NASS and NOAA "
               "data; descriptive only, with no model or forecast.",
               style={'color': '#666', 'marginTop': '0', 'fontSize': '14px'})
    ], style={'padding': '30px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderBottom': '2px solid #e0e0e0'}),

    dcc.Tabs(id="tabs", value="tab-1", children=[

        # ----- TAB 1: INDUSTRY OVERVIEW -----
        dcc.Tab(label="Industry Overview", value="tab-1", children=[
            html.Div([
                html.Div([
                    html.H3(HEADLINE, style={'marginBottom': '8px', 'lineHeight': '1.4'}),
                    html.P(html.I(
                        f"Totals cover oranges, grapefruit, tangerines, lemons and tangelos in the four states NASS "
                        f"surveys (Florida, California, Texas, Arizona), from NASS's annual state surveys. Percent "
                        f"changes are measured from each total's own peak. A total is shown only in years when every "
                        f"published fruit and state has a value."), style={'fontSize': '12px', 'color': '#888', 'marginBottom': '20px'}),
                    html.Div([
                        create_kpi_card(f"US bearing acres, peak ({ACRES_PEAK_YEAR})", ACRES_PEAK, "acres", COLORS['warning']),
                        create_kpi_card(f"US bearing acres ({LATEST_YEAR}{', prelim.' if LATEST_PRELIM else ''})", ACRES_LATEST,
                                        f"acres, {ACRES_FALL}% below the peak", COLORS['danger']),
                        create_kpi_card(f"Florida's share of US citrus value", f"{SHARE_FL_FIRST:.0f}% to {SHARE_FL_LAST:.0f}%",
                                        f"{FIRST_VALUE_YEAR} to {LATEST_YEAR}", COLORS['danger']),
                        create_kpi_card(f"California's share of US citrus value", f"{SHARE_CA_FIRST:.0f}% to {SHARE_CA_LAST:.0f}%",
                                        f"{FIRST_VALUE_YEAR} to {LATEST_YEAR}", COLORS['primary']),
                    ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'space-around'})
                ], style=CARD_STYLE),

                html.Div([dcc.Graph(figure=build_acres_by_state()), chart_hint(),
                          html.P(PRELIM_NOTE + gap_note(citrus, "bearing_acres", "The acreage total"),
                                 style=FOOTNOTE_STYLE)], style=CARD_STYLE),
                html.Div([dcc.Graph(figure=build_value_share_by_state()), chart_hint(),
                          html.P("Each bar is the share of that year's US value of production, so it compares states "
                                 "with each other and is not affected by inflation." + gap_note(citrus, "value_of_production_usd", "The value total"),
                                 style=FOOTNOTE_STYLE)], style=CARD_STYLE),
                html.Div([dcc.Graph(figure=build_value_by_fruit()), chart_hint(),
                          html.P(NOMINAL_NOTE + " Because they are not adjusted, dollar values should not be compared "
                                 "across decades as if they bought the same amount; use the share chart above for that."
                                 + gap_note(citrus, "value_of_production_usd", "The value total"),
                                 style=FOOTNOTE_STYLE)], style={**CARD_STYLE, 'marginBottom': '0'}),
            ], style={'padding': '20px'})
        ]),

        # ----- TAB 2: BY FRUIT -----
        dcc.Tab(label="By Fruit", value="tab-2", children=[
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("Fruit:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                        dcc.Dropdown(id='fruit-dropdown', options=[{'label': f, 'value': f} for f in FRUITS],
                                     value=FRUITS[0], clearable=False, searchable=False,
                                     style={'width': '200px', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                        html.Label("Measure:", style={'fontWeight': 'bold', 'margin': '0 10px 0 25px'}),
                        dcc.Dropdown(id='metric-dropdown', options=[{'label': v[0], 'value': k} for k, v in METRICS.items()],
                                     value="bearing_acres", clearable=False, searchable=False,
                                     style={'width': '340px', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                    ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap', 'gap': '6px'}),
                ], style={'padding': '15px 20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'marginBottom': '20px'}),
                html.Div([dcc.Graph(id='fruit-chart'), chart_hint(), html.Div(id='fruit-notes')], style=CARD_STYLE),
            ], style={'padding': '20px'})
        ]),

        # ----- TAB 3: BY STATE -----
        dcc.Tab(label="By State", value="tab-3", children=[
            html.Div([
                html.Div([
                    html.Label("State:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Dropdown(id='state-dropdown', options=[{'label': _state(s), 'value': s} for s in STATES],
                                 value="FL", clearable=False, searchable=False,
                                 style={'width': '200px', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                ], style={'padding': '15px 20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'marginBottom': '20px',
                          'display': 'flex', 'alignItems': 'center'}),
                html.Div([dcc.Graph(id='state-acres-chart'), chart_hint(), html.Div(id='state-acres-note')], style=CARD_STYLE),
                html.Div([dcc.Graph(id='state-value-chart'), chart_hint(), html.Div(id='state-value-note')], style=CARD_STYLE),
            ], style={'padding': '20px'})
        ]),

        # ----- TAB 4: FLORIDA FROST MAP -----
        dcc.Tab(label="Florida: Frost Map", value="tab-4", children=[
            html.Div([
                html.Div([
                    html.H3("Bloom-Season Frost Days by Weather Station (Jan-Mar)", style={'marginBottom': '8px'}),
                    html.P(html.I(
                        "A closer look inside Florida's orange industry. Each marker is a NOAA weather station, not a "
                        "county. Color and size show the mean number of days a year at or below 32 F in January-March. "
                        "Only winters with every night observed are counted, so stations have different numbers of "
                        "counted years: compare averages with that in mind."),
                        style={'fontSize': '12px', 'color': '#888', 'marginBottom': '15px'}),
                    dcc.Graph(figure=build_map_figure()),
                    html.P("Drag to move the map; scroll to zoom. Hover a marker for the station's details.",
                           style={'margin': '4px 2px 0', 'color': '#888', 'fontSize': '13px', 'fontStyle': 'italic'}),
                ], style=CARD_STYLE),
                html.Div([
                    html.H3("Station summary", style={'marginBottom': '12px'}),
                    build_station_table(),
                    html.P(STATION_NOTE + " Archbold is a notably cold site (open scrub), so its frost "
                           "counts are not representative of nearby groves.", style=FOOTNOTE_STYLE),
                ], style=CARD_STYLE),
            ], style={'padding': '20px'})
        ]),

        # ----- TAB 5: FLORIDA COUNTIES -----
        dcc.Tab(label="Florida: Counties", value="tab-5", children=[
            html.Div([
                html.Div([
                    html.P([
                        html.Strong("Note: "),
                        "USDA QuickStats has no county-level orange yield or production (checked for oranges and "
                        "citrus totals, in the survey and Census programs). NASS's Citrus Summary lists county "
                        "production, but as an apportionment of the statewide harvest, not a county measurement, so "
                        "no county yield is shown or estimated here. The panel shows Census bearing acreage and "
                        "weather from one NOAA station per county (the station, not the whole county). "
                        "Acreage totals USDA withheld are shown as gaps."
                    ], style={'fontSize': '13px', 'color': '#666', 'backgroundColor': '#fff9db', 'padding': '15px',
                              'borderRadius': '8px', 'borderLeft': '4px solid ' + COLORS['warning']})
                ], style={'marginBottom': '20px'}),

                html.Div([
                    html.Label("Counties:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Checklist(id='county-checklist', options=[{'label': f' {c}', 'value': c} for c in COUNTY_LIST],
                                  value=COUNTY_LIST, inline=True, style={'display': 'inline-block'})
                ], style={'padding': '15px 20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'marginBottom': '20px'}),

                html.Div([
                    html.H3("Frost Days During Bloom (Jan-Mar), by Station", style={'marginBottom': '20px'}),
                    dcc.Graph(id='county-frost-chart'), chart_hint(),
                    html.P(html.I(STATION_NOTE + " The legend shows how many winters each station has counted. "
                                  "Breaks in a line are years when the station was missing some January-March "
                                  "nights, or had no record: shown as missing, not as zero."), style=FOOTNOTE_STYLE)
                ], style=CARD_STYLE),

                html.Div([
                    html.H3("Bearing Acreage Trend (USDA Census years)", style={'marginBottom': '20px'}),
                    dcc.Graph(id='county-acreage-chart'), chart_hint(),
                    html.P(ACREAGE_NOTE, style=FOOTNOTE_STYLE)
                ], style=CARD_STYLE),

                html.Div([
                    html.H3("Yearly Outlook", style={'marginBottom': '20px'}),
                    html.Div([
                        html.Label("Year:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                        dcc.Dropdown(id='county-year-dropdown',
                                     options=[{'label': str(y), 'value': y} for y in COUNTY_YEARS],
                                     value=DEFAULT_OUTLOOK_YEAR, clearable=False, searchable=False,
                                     style={'width': '150px', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                        html.I(f"Opens on {DEFAULT_OUTLOOK_YEAR}, the latest year with complete data for every "
                               "county; incomplete values show as missing.",
                               style={'fontSize': '12px', 'color': '#888', 'marginLeft': '15px'})
                    ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center'}),
                    dcc.Graph(id='county-latest-comparison'), chart_hint(legend=False)
                ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'})
            ], style={'padding': '20px'})
        ])
    ])
], style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'})


# ---------------------------------------------------------------------------
# Callbacks: By Fruit
# ---------------------------------------------------------------------------
def _fruit_series(fruit, metric):
    """Per-state series for one fruit and measure, as {state: DataFrame(year, value, status)}."""
    base = "yield_boxes_per_acre" if metric == "yield_pct_of_peak" else metric
    d = citrus_plot[(citrus_plot["fruit"] == fruit) & (citrus_plot["measure"] == base)]
    out = {}
    for st, g in d.groupby("state"):
        g = g.sort_values("year").copy()
        if metric == "yield_pct_of_peak":
            g["value"] = g["value"] / g["value"].max() * 100
        elif metric in ("production_boxes", "value_of_production_usd"):
            g["value"] = g["value"] / 1e6
        out[st] = g
    return out


def _fruit_notes(fruit, metric):
    """Footnotes that say exactly which values are missing or left out, and why."""
    base = "yield_boxes_per_acre" if metric == "yield_pct_of_peak" else metric
    notes = []
    if metric == "value_of_production_usd":
        notes.append(NOMINAL_NOTE)
    if metric.startswith("yield"):
        notes.append("Box weights differ by state, so compare changes over time and each state's share of its own peak, "
                     "not raw boxes per acre across states.")
    if LATEST_PRELIM:
        notes.append(PRELIM_NOTE)
    raw = citrus[(citrus["fruit"] == fruit) & (citrus["measure"] == base)]
    gaps = []
    for st, g in raw.groupby("state"):
        blank = g[g["value"].isna()]
        if len(blank):
            gaps.append(f"{_state(st)} {cd.year_ranges(blank['year'])} (withheld or not available)")
        missing = sorted(set(range(int(g["year"].min()), int(g["year"].max()) + 1)) - set(g["year"]))
        if missing:
            gaps.append(f"{_state(st)} {cd.year_ranges(missing)} (no value published)")
    if gaps:
        notes.append("Gaps in the lines: " + "; ".join(gaps) + ". Nothing is estimated.")
    ends = [f"{_state(st)} after {int(g['year'].max())}" for st, g in raw.groupby("state") if g["year"].max() < LATEST_YEAR]
    if ends:
        notes.append("NASS publishes no data for " + "; ".join(ends) + ".")
    if metric.startswith("yield"):
        for _, r in conflicts[conflicts["fruit"] == fruit].iterrows():
            cite = cd.CONFLICT_CITATIONS.get((r["fruit"], r["state"], int(r["year"])), "")
            notes.append(f"Gap: {_state(r['state'])} {fruit.lower()} {int(r['year'])}. NASS's QuickStats publishes "
                         f"{r['published']:.0f} boxes per acre, but its own utilized production and bearing acres in the "
                         f"same database imply about {r['implied']:.0f}. Shown as a gap, not corrected; the published "
                         f"value stays in the data file. {cite}".strip())
    return html.Div([html.P(n, style=FOOTNOTE_STYLE) for n in notes])


@app.callback(
    [Output('fruit-chart', 'figure'), Output('fruit-notes', 'children')],
    [Input('fruit-dropdown', 'value'), Input('metric-dropdown', 'value')]
)
def update_fruit(fruit, metric):
    label, fmt = METRICS[metric]
    fig = go.Figure()
    for st, g in _fruit_series(fruit, metric).items():
        symbols = ["circle-open" if s == "preliminary" else "circle" for s in g["status"]]
        fig.add_trace(go.Scatter(
            x=g["year"], y=g["value"], mode="lines+markers", connectgaps=False, name=_state(st),
            line=dict(color=STATE_COLORS.get(st), width=2),
            marker=dict(size=[10 if s == "preliminary" else 5 for s in g["status"]], symbol=symbols,
                        line=dict(width=2, color=STATE_COLORS.get(st))),
            hovertemplate=f"<b>%{{x}}</b><br>{_state(st)}: %{{y:{fmt}}}<extra></extra>"))
    fig.update_layout(title=f"{fruit}: {label}", xaxis_title="Season (end year)", yaxis_title=label, height=480,
                      template="plotly_white", hovermode="x unified")
    _shade_latest(fig)
    return fig, _fruit_notes(fruit, metric)


# ---------------------------------------------------------------------------
# Callbacks: By State
# ---------------------------------------------------------------------------
def _state_stack(state, measure, scale, ytitle, title, hover_fmt, note_prefix):
    by_fruit = cd.complete_total(citrus, measure, by="fruit", state=state)
    by_fruit = by_fruit[[f for f in cd.FRUIT_ORDER if f in by_fruit.columns]]
    fig = stacked_bars(by_fruit, title, ytitle, scale, FRUIT_COLORS, lambda f: f, hover_fmt)
    years = cd.incomplete_years(citrus, measure, state)
    notes = [note_prefix] if note_prefix else []
    if LATEST_PRELIM:
        notes.append(PRELIM_NOTE)
    if years:
        notes.append(f"Left empty in {cd.year_ranges(years)}: NASS withheld or did not publish a value for at least one "
                     f"fruit in {_state(state)}, and a partial stack would understate it.")
    return fig, html.Div([html.P(n, style=FOOTNOTE_STYLE) for n in notes])


@app.callback(
    [Output('state-acres-chart', 'figure'), Output('state-acres-note', 'children'),
     Output('state-value-chart', 'figure'), Output('state-value-note', 'children')],
    Input('state-dropdown', 'value')
)
def update_state(state):
    name = _state(state)
    a_fig, a_note = _state_stack(state, "bearing_acres", 1e3, "Bearing acres (thousands)",
                                 f"{name}: Bearing Acres, by Fruit", ",.1f", "")
    v_fig, v_note = _state_stack(state, "value_of_production_usd", 1e6, "Value of production ($ million, nominal)",
                                 f"{name}: Value of Production, by Fruit", ",.0f", NOMINAL_NOTE)
    return a_fig, a_note, v_fig, v_note


# ---------------------------------------------------------------------------
# Callbacks: Florida counties
# ---------------------------------------------------------------------------
def _legend_name(county):
    r = station_info.loc[county]
    return f"{county} - {r['station_label']} ({int(r['years_counted'])} of {int(r['years_in_range'])} winters)"


@app.callback(Output('county-frost-chart', 'figure'), Input('county-checklist', 'value'))
def update_county_frost(selected_counties):
    """Frost days by bloom season, one line per selected station."""
    fig = go.Figure()
    for county in selected_counties:
        sub = county_features[county_features['county_name'] == county].sort_values('year')
        fig.add_trace(go.Scatter(
            x=sub['year'], y=sub['frost_days_bloom'], mode='lines+markers', name=_legend_name(county),
            line=dict(color=COUNTY_COLORS.get(county), width=2), marker=dict(size=5)))
    # Say which stations have no 2010 value instead of implying all were measured.
    in_2010 = county_features[county_features['year'] == 2010]
    no_2010 = sorted(in_2010.loc[in_2010['frost_days_bloom'].isna(), 'county_name'])
    freeze_note = (f"({', '.join(no_2010)}: 2010 record incomplete)" if no_2010 else "(all stations recorded frost)")
    fig.add_annotation(x=2010, y=in_2010['frost_days_bloom'].max(), text=f"Jan 2010 FL freeze<br>{freeze_note}",
                       showarrow=True, arrowhead=2, ax=40, ay=-40, font=dict(size=11, color='#666'))
    fig.update_layout(xaxis_title="Year (January-March of that year)", yaxis_title="Frost Days (Jan-Mar, TMIN <= 32°F)",
                      hovermode='x unified', height=470, template='plotly_white',
                      legend=dict(orientation="h", yanchor="top", y=-0.2))
    return fig


@app.callback(Output('county-acreage-chart', 'figure'), Input('county-checklist', 'value'))
def update_county_acreage(selected_counties):
    """Bearing acreage trend, Census years only, per county. Withheld totals are blank, so the line breaks."""
    fig = go.Figure()
    for county in selected_counties:
        sub = county_features[(county_features['county_name'] == county) & (county_features['acreage_status'].notna())
                              ].sort_values('year')
        fig.add_trace(go.Scatter(
            x=sub['year'], y=sub['bearing_acres'], mode='lines+markers', connectgaps=False, name=county,
            line=dict(color=COUNTY_COLORS.get(county), width=2, dash='dot'), marker=dict(size=9)))
    fig.update_layout(xaxis_title="Census Year", yaxis_title="Bearing Acres (ORANGES)", hovermode='x unified',
                      height=450, template='plotly_white')
    return fig


@app.callback(Output('county-latest-comparison', 'figure'),
              [Input('county-checklist', 'value'), Input('county-year-dropdown', 'value')])
def update_county_latest(selected_counties, selected_year):
    """Bar comparison of key indicators for a user-selected year (three subplots: very different scales)."""
    sub = county_features[(county_features['year'] == selected_year) & (county_features['county_name'].isin(selected_counties))]
    fig = make_subplots(rows=1, cols=3, subplot_titles=("Frost Days During Bloom (Jan-Mar)", "Avg Max Temp (°F)",
                                                        "GDD (Growing Degree Days)"))
    counties_ordered = [c for c in selected_counties if not sub[sub['county_name'] == c].empty]
    if not counties_ordered:
        fig.update_layout(title=f"{selected_year} Snapshot — select at least one county", height=450, template='plotly_white')
        return fig

    colors = [COUNTY_COLORS.get(c) for c in counties_ordered]
    pick = lambda col: [sub[sub['county_name'] == c][col].values[0] for c in counties_ordered]
    frost_vals, tmax_vals, gdd_vals = pick('frost_days_bloom'), pick('tmax_mean_grow'), pick('gdd_total_grow')

    # A value is NA when the station was missing too many days in the window: "missing", not zero.
    def bar_data(values, fmt):
        return ([0 if pd.isna(v) else v for v in values],
                ["<i>missing</i>" if pd.isna(v) else format(v, fmt) for v in values])

    def axis_top(values, factor, floor):
        present = [v for v in values if not pd.isna(v)]
        return max(floor, max(present) * factor) if present else floor

    for col, values, fmt in ((1, frost_vals, ".0f"), (2, tmax_vals, ".1f"), (3, gdd_vals, ".0f")):
        y, text = bar_data(values, fmt)
        fig.add_trace(go.Bar(x=counties_ordered, y=y, text=text, textposition='outside',
                             marker=dict(color=colors), showlegend=False), row=1, col=col)
    fig.update_yaxes(range=[0, axis_top(frost_vals, 1.3, 2)], row=1, col=1)
    fig.update_yaxes(range=[0, axis_top(tmax_vals, 1.15, 1)], row=1, col=2)
    fig.update_yaxes(range=[0, axis_top(gdd_vals, 1.15, 1)], row=1, col=3)

    frost_present = [v for v in frost_vals if not pd.isna(v)]
    n_missing = len(frost_vals) - len(frost_present)
    if not frost_present:
        frost_note = " — frost data missing for every selected county"
    elif max(frost_present) == 0 and n_missing == 0:
        frost_note = " — no frost recorded in any selected county"
    elif max(frost_present) == 0:
        n_with = len(frost_present)
        frost_note = (f" — no frost in the {n_with} {'county' if n_with == 1 else 'counties'} "
                      f"with data ({n_missing} missing)")
    else:
        frost_note = ""
    fig.update_layout(title=f"{selected_year} Snapshot" + frost_note, height=450, template='plotly_white')
    return fig


# Expose Flask server for Gunicorn (Render, Heroku, etc.)
server = app.server

if __name__ == "__main__":
    print("[OK] Starting Dash app at http://127.0.0.1:8050")
    print("Press Ctrl+C to stop.")
    app.run(debug=False, port=8050, host="127.0.0.1")
