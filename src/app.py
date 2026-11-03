"""
Plotly Dash app: Florida orange yield, county acreage and winter frost by
weather station. Descriptive only; no model, no forecast.
3 tabs: Overview, Frost Map, County Comparison.
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# ---------------------------------------------------------------------------
# Data (all committed CSVs; see docs/SCHEMA.md)
# ---------------------------------------------------------------------------
yield_df = pd.read_csv("data/nass_yield.csv").sort_values("year").reset_index(drop=True)
county_features = pd.read_csv("data/county_features.csv")
stations = pd.read_csv("data/stations.csv")
frost_summary = pd.read_csv("data/station_frost_summary.csv")

COUNTY_LIST = sorted(county_features["county_name"].unique().tolist())
COUNTY_YEARS = sorted(county_features["year"].unique().tolist())
COUNTY_COLORS = {
    "Polk": "#0d6efd",
    "Hendry": "#198754",
    "DeSoto": "#fd7e14",
    "Highlands": "#6f42c1",
}

COLORS = {
    'background': '#f8f9fa',
    'text': '#212529',
    'primary': '#0d6efd',
    'success': '#198754',
    'warning': '#ffc107',
    'danger': '#dc3545'
}

# One row per county: its station, where NOAA lists it, and its frost summary.
station_info = (
    stations.rename(columns={"panel_county": "county_name"})
    .merge(frost_summary, on="county_name", how="left")
    .set_index("county_name")
)

# ---------------------------------------------------------------------------
# Yield story, computed from the data
# ---------------------------------------------------------------------------
_peak = yield_df.loc[yield_df["yield_lbs_acre"].idxmax()]
_low = yield_df.loc[yield_df["yield_lbs_acre"].idxmin()]
_latest = yield_df.iloc[-1]
PEAK_YEAR, PEAK_YIELD = int(_peak["year"]), float(_peak["yield_lbs_acre"])
LOW_YEAR, LOW_YIELD = int(_low["year"]), float(_low["yield_lbs_acre"])
LATEST_YEAR, LATEST_YIELD = int(_latest["year"]), float(_latest["yield_lbs_acre"])
LATEST_PRELIM = _latest["status"] == "preliminary"
FALL_PCT = round((1 - LOW_YIELD / PEAK_YIELD) * 100)
LATEST_BELOW_PCT = round((1 - LATEST_YIELD / PEAK_YIELD) * 100)

# "Frost stayed flat" is only said if every station's straight-line trend is
# within one frost day per decade; otherwise the headline says it varied.
FROST_FLAT = bool((frost_summary["trend_days_per_decade"].abs() < 1).all())
FROST_CLAUSE = ("winter frost at the stations measured stayed flat" if FROST_FLAT
                else "winter frost at the stations measured varied from station to station")

if LATEST_YEAR > LOW_YEAR and LATEST_YIELD > LOW_YIELD:
    HEADLINE = (
        f"Florida's orange yield fell {FALL_PCT}% from its {PEAK_YEAR} peak to its {LOW_YEAR} low and has "
        f"recovered only partly ({LATEST_YEAR}"
        + (" preliminary" if LATEST_PRELIM else "")
        + f": {LATEST_BELOW_PCT}% below the peak), while {FROST_CLAUSE}."
    )
else:
    HEADLINE = (f"Florida's orange yield fell {FALL_PCT}% from its {PEAK_YEAR} peak to {LOW_YEAR}, "
                f"while {FROST_CLAUSE}.")

# ---------------------------------------------------------------------------
# County panel pieces
# ---------------------------------------------------------------------------
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
    + (
        " Gaps are totals USDA withheld (marked '(D)' in the Census, to avoid disclosing "
        f"individual operations' data): {WITHHELD_NOTE}. They are not estimated."
        if WITHHELD_NOTE else ""
    )
)

app = dash.Dash(__name__)

KPI_STYLE = {
    'textAlign': 'center',
    'padding': '20px',
    'backgroundColor': 'white',
    'borderRadius': '8px',
    'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
    'margin': '10px'
}
CARD_STYLE = {'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}
FOOTNOTE_STYLE = {'fontSize': '12px', 'color': '#888', 'marginTop': '10px'}


def create_kpi_card(label, value, unit="", color=COLORS['primary']):
    """Create a KPI card component."""
    return html.Div([
        html.H4(label, style={'color': '#666', 'fontSize': '14px', 'marginBottom': '10px'}),
        html.H2(f"{value:,.0f}" if isinstance(value, (int, float)) else value,
                style={'color': color, 'marginBottom': '5px'}),
        html.P(unit, style={'color': '#999', 'fontSize': '12px'})
    ], style=KPI_STYLE)


CHART_HINT_ZOOM = "Drag to zoom into part of the chart; double-click the chart to reset the view."
CHART_HINT_LEGEND = " Click a legend entry to hide that series; double-click it to isolate it."


def chart_hint(legend=True):
    """Small caption under a chart explaining zoom/legend interactions."""
    text = CHART_HINT_ZOOM + (CHART_HINT_LEGEND if legend else "")
    return html.P(text, style={'margin': '4px 2px 0', 'color': '#888', 'fontSize': '13px', 'fontStyle': 'italic'})


# ---------------------------------------------------------------------------
# Static figures (do not depend on any input)
# ---------------------------------------------------------------------------
def build_yield_figure():
    """Statewide yield; the preliminary point is drawn hollow and joined with a dashed line."""
    reported = yield_df[yield_df["status"] != "preliminary"]
    prelim = yield_df[yield_df["status"] == "preliminary"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=reported["year"], y=reported["yield_lbs_acre"], mode="lines+markers", name="NASS reported",
        line=dict(color=COLORS['primary'], width=2), marker=dict(size=6),
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} lb/acre<extra></extra>"))
    if len(prelim) and len(reported):
        join = pd.concat([reported.tail(1), prelim])
        fig.add_trace(go.Scatter(
            x=join["year"], y=join["yield_lbs_acre"], mode="lines+markers", name="Preliminary (NASS, August)",
            line=dict(color=COLORS['primary'], width=2, dash="dash"),
            marker=dict(size=[0, 11], symbol="circle-open", line=dict(width=2)),
            hovertemplate="<b>%{x} (preliminary)</b><br>%{y:,.0f} lb/acre<extra></extra>"))
    fig.add_annotation(x=PEAK_YEAR, y=PEAK_YIELD, text=f"{PEAK_YEAR} peak", showarrow=True, ay=-30)
    fig.add_annotation(x=LOW_YEAR, y=LOW_YIELD, text=f"{LOW_YEAR} low (-{FALL_PCT}%)", showarrow=True, ay=40)
    fig.update_layout(
        title="Florida Orange Yield (statewide)", xaxis_title="Season (NASS labels a season by its end year)",
        yaxis_title="Yield (lb/acre)", height=480, template="plotly_white", hovermode="x unified")
    return fig


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
                    cmin=0, showscale=True, opacity=0.85,
                    colorbar=dict(title="Mean frost<br>days a year")),
        hovertext=hover, hoverinfo="text"))
    fig.update_layout(
        map=dict(style="open-street-map", center=dict(lat=float(df["latitude"].mean()), lon=float(df["longitude"].mean())), zoom=6.6),
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
app.layout = html.Div([
    html.Div([
        html.H1("Florida Orange Yield, Acreage and Winter Frost", style={
            'color': COLORS['primary'], 'marginBottom': '10px', 'fontSize': '32px', 'fontWeight': 'bold'}),
        html.P("What happened to Florida's orange yield and acreage, and does winter frost explain it?",
               style={'color': '#333', 'margin': '0 0 6px', 'fontSize': '16px'}),
        html.P("For anyone following the decline of Florida's orange industry, including analysts and students. "
               "Real USDA NASS and NOAA data; descriptive only, with no model or forecast.",
               style={'color': '#666', 'marginTop': '0', 'fontSize': '14px'})
    ], style={'padding': '30px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderBottom': '2px solid #e0e0e0'}),

    dcc.Tabs(id="tabs", value="tab-1", children=[

        # ----- TAB 1: OVERVIEW -----
        dcc.Tab(label="Overview", value="tab-1", children=[
            html.Div([
                html.Div([
                    html.H3(HEADLINE, style={'marginBottom': '8px', 'lineHeight': '1.4'}),
                    html.P(html.I(
                        f"The {FALL_PCT}% is measured from the {PEAK_YEAR} peak. Yield is published only statewide, "
                        "so the yield chart is statewide; county panels cover Census acreage and weather from one "
                        "station per county. Winter frost means days at or below 32 F in January-March, per station."),
                        style={'fontSize': '12px', 'color': '#888', 'marginBottom': '20px'}),
                    html.Div([
                        create_kpi_card(f"Peak ({PEAK_YEAR})", PEAK_YIELD, "lb/acre", COLORS['warning']),
                        create_kpi_card(f"Low ({LOW_YEAR})", LOW_YIELD, f"lb/acre, {FALL_PCT}% below the peak", COLORS['danger']),
                        create_kpi_card(f"Latest ({LATEST_YEAR}{', preliminary' if LATEST_PRELIM else ''})", LATEST_YIELD,
                                        f"lb/acre, {LATEST_BELOW_PCT}% below the peak", COLORS['primary']),
                    ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'space-around'})
                ], style=CARD_STYLE),

                html.Div([
                    dcc.Graph(figure=build_yield_figure()),
                    chart_hint(),
                    html.P(
                        "NASS publishes the most recent season as a preliminary estimate each August and revises it "
                        "a year later. Seasons are labeled by their end year (2023 is the 2022-23 season). "
                        "Frost is not drawn on this chart because frost years are calendar years, not seasons.",
                        style=FOOTNOTE_STYLE)
                ], style=CARD_STYLE),
            ], style={'padding': '20px'})
        ]),

        # ----- TAB 2: FROST MAP -----
        dcc.Tab(label="Frost Map", value="tab-2", children=[
            html.Div([
                html.Div([
                    html.H3("Bloom-Season Frost Days by Weather Station (Jan-Mar)", style={'marginBottom': '8px'}),
                    html.P(html.I(
                        "Each marker is a NOAA weather station, not a county. Color and size show the mean number of "
                        "days a year at or below 32 F in January-March. Only winters with every night observed are "
                        "counted, so stations have different numbers of counted years: compare averages with that in mind."),
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

        # ----- TAB 3: COUNTY COMPARISON -----
        dcc.Tab(label="County Comparison", value="tab-3", children=[
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
                    ], style={'fontSize': '13px', 'color': '#666', 'backgroundColor': '#fff9db',
                              'padding': '15px', 'borderRadius': '8px', 'borderLeft': '4px solid ' + COLORS['warning']})
                ], style={'marginBottom': '20px'}),

                html.Div([
                    html.Label("Counties:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Checklist(
                        id='county-checklist',
                        options=[{'label': f' {c}', 'value': c} for c in COUNTY_LIST],
                        value=COUNTY_LIST, inline=True, style={'display': 'inline-block'})
                ], style={'padding': '15px 20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'marginBottom': '20px'}),

                html.Div([
                    html.H3("Frost Days During Bloom (Jan-Mar), by Station", style={'marginBottom': '20px'}),
                    dcc.Graph(id='county-frost-chart'),
                    chart_hint(),
                    html.P(html.I(STATION_NOTE + " The legend shows how many winters each station has counted. "
                                  "Breaks in a line are years when the station was missing some January-March "
                                  "nights, or had no record: shown as missing, not as zero."), style=FOOTNOTE_STYLE)
                ], style=CARD_STYLE),

                html.Div([
                    html.H3("Bearing Acreage Trend (USDA Census years)", style={'marginBottom': '20px'}),
                    dcc.Graph(id='county-acreage-chart'),
                    chart_hint(),
                    html.P(ACREAGE_NOTE, style=FOOTNOTE_STYLE)
                ], style=CARD_STYLE),

                html.Div([
                    html.H3("Yearly Outlook", style={'marginBottom': '20px'}),
                    html.Div([
                        html.Label("Year:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                        dcc.Dropdown(
                            id='county-year-dropdown',
                            options=[{'label': str(y), 'value': y} for y in COUNTY_YEARS],
                            value=DEFAULT_OUTLOOK_YEAR, clearable=False, searchable=False,
                            style={'width': '150px', 'display': 'inline-block', 'verticalAlign': 'middle'}),
                        html.I(f"Opens on {DEFAULT_OUTLOOK_YEAR}, the latest year with complete data for every "
                               "county; incomplete values show as missing.",
                               style={'fontSize': '12px', 'color': '#888', 'marginLeft': '15px'})
                    ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center'}),
                    dcc.Graph(id='county-latest-comparison'),
                    chart_hint(legend=False)
                ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'})

            ], style={'padding': '20px'})
        ])
    ])
], style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'})


# ---------------------------------------------------------------------------
# Callbacks (County Comparison tab)
# ---------------------------------------------------------------------------
def _legend_name(county):
    r = station_info.loc[county]
    return f"{county} - {r['station_label']} ({int(r['years_counted'])} of {int(r['years_in_range'])} winters)"


@app.callback(
    Output('county-frost-chart', 'figure'),
    Input('county-checklist', 'value')
)
def update_county_frost(selected_counties):
    """Frost days by bloom season, one line per selected station."""
    fig = go.Figure()

    for county in selected_counties:
        sub = county_features[county_features['county_name'] == county].sort_values('year')
        fig.add_trace(go.Scatter(
            x=sub['year'], y=sub['frost_days_bloom'], mode='lines+markers', name=_legend_name(county),
            line=dict(color=COUNTY_COLORS.get(county), width=2), marker=dict(size=5)
        ))

    # Say which stations have no 2010 value instead of implying all were measured.
    in_2010 = county_features[county_features['year'] == 2010]
    no_2010 = sorted(in_2010.loc[in_2010['frost_days_bloom'].isna(), 'county_name'])
    freeze_note = (f"({', '.join(no_2010)}: 2010 record incomplete)" if no_2010
                   else "(all stations recorded frost)")
    fig.add_annotation(
        x=2010, y=in_2010['frost_days_bloom'].max(),
        text=f"Jan 2010 FL freeze<br>{freeze_note}",
        showarrow=True, arrowhead=2, ax=40, ay=-40, font=dict(size=11, color='#666'))

    fig.update_layout(
        xaxis_title="Year (January-March of that year)", yaxis_title="Frost Days (Jan-Mar, TMIN <= 32°F)",
        hovermode='x unified', height=470, template='plotly_white',
        legend=dict(orientation="h", yanchor="top", y=-0.2))
    return fig


@app.callback(
    Output('county-acreage-chart', 'figure'),
    Input('county-checklist', 'value')
)
def update_county_acreage(selected_counties):
    """Bearing acreage trend, Census years only, per county.

    Every Census year is plotted; where USDA withheld the total the value is
    blank, so the line breaks instead of bridging the gap.
    """
    fig = go.Figure()

    for county in selected_counties:
        sub = county_features[
            (county_features['county_name'] == county) & (county_features['acreage_status'].notna())
        ].sort_values('year')
        fig.add_trace(go.Scatter(
            x=sub['year'], y=sub['bearing_acres'], mode='lines+markers', connectgaps=False, name=county,
            line=dict(color=COUNTY_COLORS.get(county), width=2, dash='dot'), marker=dict(size=9)
        ))

    fig.update_layout(
        xaxis_title="Census Year", yaxis_title="Bearing Acres (ORANGES)",
        hovermode='x unified', height=450, template='plotly_white')
    return fig


@app.callback(
    Output('county-latest-comparison', 'figure'),
    [Input('county-checklist', 'value'),
     Input('county-year-dropdown', 'value')]
)
def update_county_latest(selected_counties, selected_year):
    """Bar comparison of key indicators for a user-selected year.

    Uses 3 separate subplots (not one grouped bar chart) because
    frost days (0-25), temp (85-95F), and GDD (3800-4300) live on
    wildly different scales - combining them in one chart made the
    smaller-scale bars visually disappear next to GDD.
    """
    sub = county_features[
        (county_features['year'] == selected_year) & (county_features['county_name'].isin(selected_counties))
    ]

    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=("Frost Days During Bloom (Jan-Mar)", "Avg Max Temp (°F)", "GDD (Growing Degree Days)")
    )

    counties_ordered = [c for c in selected_counties if not sub[sub['county_name'] == c].empty]

    if not counties_ordered:
        fig.update_layout(title=f"{selected_year} Snapshot — select at least one county", height=450, template='plotly_white')
        return fig

    colors = [COUNTY_COLORS.get(c) for c in counties_ordered]

    frost_vals = [sub[sub['county_name'] == c]['frost_days_bloom'].values[0] for c in counties_ordered]
    tmax_vals = [sub[sub['county_name'] == c]['tmax_mean_grow'].values[0] for c in counties_ordered]
    gdd_vals = [sub[sub['county_name'] == c]['gdd_total_grow'].values[0] for c in counties_ordered]

    # A value is NA when the station was missing too many days in the window.
    # That is "missing", not zero: it gets no bar and an italic label. A real
    # zero keeps its bar and a "0" label so it can't be mistaken for it.
    def bar_data(values, fmt):
        y = [0 if pd.isna(v) else v for v in values]
        text = ["<i>missing</i>" if pd.isna(v) else format(v, fmt) for v in values]
        return y, text

    def axis_top(values, factor, floor):
        # Explicit headroom above the tallest bar so the "outside" label has
        # room (Plotly's autorange leaves ~5%, which clipped labels), and a
        # floor so an all-zero or all-missing panel still gets a readable axis.
        present = [v for v in values if not pd.isna(v)]
        return max(floor, max(present) * factor) if present else floor

    for col, values, fmt in ((1, frost_vals, ".0f"), (2, tmax_vals, ".1f"), (3, gdd_vals, ".0f")):
        y, text = bar_data(values, fmt)
        fig.add_trace(go.Bar(
            x=counties_ordered, y=y, text=text, textposition='outside',
            marker=dict(color=colors), showlegend=False
        ), row=1, col=col)

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
