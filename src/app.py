"""
Plotly Dash app: the US citrus industry by fruit and state (acreage, yield,
price and value of production, 1990-2026), from USDA NASS state surveys.
Descriptive only; no model, no forecast.

Tabs: Industry Overview, By Fruit, By State. Every chart has a collapsed "About this chart" section
(what it shows, definitions, scope, caveats, tips) and a count of the NASS values behind it.
`/healthz` and `/debugz` are for the host (see docs/METHODOLOGY.md, Deployment notes).
"""

import datetime
import importlib.metadata
import os
import platform
import sys
import time

import dash
from dash import dcc, html, Input, Output
from flask import jsonify
import plotly.graph_objects as go
import pandas as pd

try:                                  # gunicorn src.app:server and run_dashboard.py import it as a package
    from src import citrus_data as cd
    from src import manifest
except ImportError:                   # python src/app.py
    import citrus_data as cd
    import manifest

STARTED = time.time()
STARTED_AT = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

# ---------------------------------------------------------------------------
# Data (all committed CSVs; see docs/SCHEMA.md)
# ---------------------------------------------------------------------------
citrus = cd.load_citrus("data/citrus_by_state.csv")
totals = cd.load_totals("data/citrus_totals_by_state.csv")      # NASS's own state totals, 2008 on
citrus_plot = cd.blank_conflicts(citrus)          # flagged yields drawn as gaps; the file is untouched
conflicts = cd.yield_conflicts(citrus)
TOTALS_FIRST_YEAR = int(totals["year"].min())
cpi = cd.load_cpi("data/cpi_u_monthly.csv")                    # BLS CPI-U, for constant dollars
FACTORS = cd.real_factors(cpi)                                 # nominal -> BASE_YEAR dollars, by season
BASE_YEAR = cd.BASE_YEAR

PULLED = {k: v["pulled"] for k, v in manifest.load("data/manifest.json").items()}      # when each file was pulled
SOURCE_NOTICE = (
    f"Data: USDA National Agricultural Statistics Service (NASS), Quick Stats, pulled {PULLED['data/citrus_by_state.csv']}; "
    f"US Bureau of Labor Statistics (BLS), consumer price index CPI-U, retrieved {PULLED['data/cpi_u_monthly.csv']}. "
    "This product uses the NASS API but is not endorsed or certified by NASS. BLS.gov cannot vouch for the data or "
    "analyses derived from these data after the data have been retrieved from BLS.gov.")

LATEST_YEAR = int(citrus["year"].max())
LATEST_PRELIM = bool((citrus.loc[citrus["year"] == LATEST_YEAR, "status"] == "preliminary").all())
PRELIM_TAG = " (preliminary)" if LATEST_PRELIM else ""

STATE_COLORS = {"FL": "#fd7e14", "CA": "#0d6efd", "TX": "#198754", "AZ": "#6f42c1"}
FRUIT_COLORS = {"Oranges": "#fd7e14", "Grapefruit": "#e8537a", "Tangerines": "#f2b705",
                "Lemons": "#9ec31a", "Tangelos": "#8d6e63"}
COLORS = {'background': '#f8f9fa', 'text': '#212529', 'primary': '#0d6efd', 'success': '#198754',
          'warning': '#ffc107', 'danger': '#dc3545'}

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def _cpi_gap_sentence():
    """Names each month BLS did not publish and the season whose average therefore uses 11 months."""
    parts = [f"{MONTHS[int(r.month) - 1]} {int(r.year)} (season {int(r.year) + (r.month >= 10)})" for r in cpi[cpi["cpi"].isna()].itertuples()]
    return f"BLS published no CPI-U value for {', '.join(parts)}; that season's average uses its other 11 months." if parts else ""


# ---------------------------------------------------------------------------
# Wording shared by the charts: definitions, and the notes every chart of a kind carries
# ---------------------------------------------------------------------------
DEF_BEARING = "Bearing acres are acres of citrus trees old enough to bear fruit."
DEF_UTILIZED = ("Utilized production is the part of the crop that was used, sold fresh or processed, counted in boxes; "
                "box weights differ by fruit and state.")
DEF_VALUE = ("Value of production is the utilized crop valued at the packinghouse-door price, the price at the point of "
             "first sale after packing costs are taken out.")
DEF_PRICE = "Price per box is NASS's marketing-year average price at the packinghouse door."
DEF_YIELD = "Yield is utilized boxes per bearing acre."

NOMINAL_NOTE = ("Dollar values are as reported by NASS, not adjusted for inflation, and use NASS's packinghouse-door "
                "equivalent basis.")
REAL_NOTE = (f"Dollar values are in {BASE_YEAR} dollars: each season's value is multiplied by the consumer price index "
             f"(BLS CPI-U, all items) for the {BASE_YEAR} season divided by the index for its own season, each averaged "
             f"over October to September. The index measures general purchasing power, not citrus prices. Values use "
             f"NASS's packinghouse-door equivalent basis.")
DOLLAR_METRICS = ("value_of_production_usd", "price_usd_per_box")
PRELIM_NOTE = (f"{LATEST_YEAR} is NASS's preliminary estimate for the season ending that year and is revised a "
               "year later. Seasons are labeled by their end year (2023 is the 2022-23 season).")
TOTALS_NOTE = (f"Totals use NASS's own published state totals from {TOTALS_FIRST_YEAR} and, before that, the sum of "
               "the fruit values (the two agree where both exist; see the Methodology).")
HINTS = ["Drag to zoom into part of the chart; double-click the chart to reset the view.",
         "Click a legend entry to hide that series; double-click it to isolate it."]


def dollar_notes(real):
    notes = [REAL_NOTE if real else NOMINAL_NOTE]
    if real:
        notes.append(_cpi_gap_sentence())
    return [n for n in notes if n]


def _state(code):
    return cd.STATE_NAMES.get(code, code)


# ---------------------------------------------------------------------------
# Industry summary, computed from the data. Totals use NASS's published state totals from 2008 and
# the sum of the fruit values before that; a year with a missing part has no total.
# ---------------------------------------------------------------------------
acres_total_all = cd.combined_total(citrus, totals, "bearing_acres")
value_total_all = cd.combined_total(citrus, totals, "value_of_production_usd")
acres_total, value_total = acres_total_all.dropna(), value_total_all.dropna()
acres_by_state = cd.combined_total(citrus, totals, "bearing_acres", by="state")
value_by_state = cd.combined_total(citrus, totals, "value_of_production_usd", by="state")

ACRES_PEAK_YEAR, ACRES_PEAK = int(acres_total.idxmax()), float(acres_total.max())
ACRES_LATEST = float(acres_total.loc[LATEST_YEAR])
ACRES_FALL = round(-cd.pct_change(ACRES_LATEST, ACRES_PEAK))

# Each state's share of the US value of production in the same year. Shares compare states with
# each other, so inflation cancels out (the dollar totals themselves are nominal).
value_share = value_by_state.div(value_by_state.sum(axis=1), axis=0) * 100
FIRST_VALUE_YEAR = 1990
SHARE_FL_FIRST, SHARE_FL_LAST = value_share.loc[FIRST_VALUE_YEAR, "FL"], value_share.loc[LATEST_YEAR, "FL"]
SHARE_CA_FIRST, SHARE_CA_LAST = value_share.loc[FIRST_VALUE_YEAR, "CA"], value_share.loc[LATEST_YEAR, "CA"]

# Where the acres went: Florida's decline against California's near-constant acreage (no acres moved to California)
_fl_acres, _ca_acres = acres_by_state["FL"], acres_by_state["CA"]
FL_ACRES_FALL = round(-cd.pct_change(_fl_acres.loc[LATEST_YEAR], _fl_acres.loc[ACRES_PEAK_YEAR]))
FL_LOSS_SHARE = round((_fl_acres.loc[ACRES_PEAK_YEAR] - _fl_acres.loc[LATEST_YEAR]) / (ACRES_PEAK - ACRES_LATEST) * 100)
CA_BELOW_PEAK = round(-cd.pct_change(_ca_acres.loc[LATEST_YEAR], _ca_acres.max()))

HEADLINE = (
    f"US citrus bearing acreage fell {ACRES_FALL}% from its {ACRES_PEAK_YEAR} peak to {LATEST_YEAR}{PRELIM_TAG}, and "
    f"{FL_LOSS_SHARE}% of the acres lost were in Florida, where acreage fell {FL_ACRES_FALL}% while California's is "
    f"{CA_BELOW_PEAK}% below its own peak. Over the same period Florida's share of the value of production fell from "
    f"{SHARE_FL_FIRST:.0f}% in {FIRST_VALUE_YEAR} to {SHARE_FL_LAST:.0f}% in {LATEST_YEAR}, while California's rose from "
    f"{SHARE_CA_FIRST:.0f}% to {SHARE_CA_LAST:.0f}%."
)

app = dash.Dash(__name__, title="US Citrus Industry Dashboard")

KPI_STYLE = {'textAlign': 'center', 'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px',
             'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'margin': '10px'}
CARD_STYLE = {'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}
COUNT_STYLE = {'fontSize': '12px', 'color': '#666', 'margin': '8px 2px 0'}
ABOUT_STYLE = {'margin': '6px 2px 0', 'fontSize': '13px', 'color': '#666'}
SMALL_N = 30                                    # a chart resting on fewer values than this carries an asterisk


def create_kpi_card(label, value, unit="", color=COLORS['primary']):
    return html.Div([
        html.H4(label, style={'color': '#666', 'fontSize': '14px', 'marginBottom': '10px'}),
        html.H2(value if isinstance(value, str) else f"{value:,.0f}", style={'color': color, 'marginBottom': '5px'}),
        html.P(unit, style={'color': '#999', 'fontSize': '12px'})
    ], style=KPI_STYLE)


def count_line(n):
    """The number of NASS values behind a chart; under SMALL_N it carries an asterisk with a tooltip."""
    parts = [f"n = {n:,} NASS values behind this chart"]
    if n < SMALL_N:
        parts.append(html.Abbr("*", title=f"Fewer than {SMALL_N} values: read the pattern with caution.",
                               style={'textDecoration': 'none', 'cursor': 'help', 'marginLeft': '2px', 'fontWeight': 'bold'}))
    return html.P(parts, style=COUNT_STYLE)


def about(items):
    """Collapsed 'About this chart' section: every explanatory line for the chart, as italic bullets."""
    return html.Details([
        html.Summary("About this chart", style={'cursor': 'pointer', 'fontWeight': 'bold'}),
        html.Ul([html.Li(html.I(i)) for i in items if i], style={'margin': '6px 0 0', 'paddingLeft': '22px'}),
    ], style=ABOUT_STYLE)


def chart_footer(n, items):
    """What sits under a chart: its collapsed 'About this chart' section, then the count behind it."""
    return html.Div([about(items), count_line(n)])


# ---------------------------------------------------------------------------
# Chart builders for the industry tabs
# ---------------------------------------------------------------------------
def _shade_latest(fig):
    """Light band over the preliminary season."""
    if LATEST_PRELIM:
        fig.add_vrect(x0=LATEST_YEAR - 0.5, x1=LATEST_YEAR + 0.5, fillcolor="grey", opacity=0.15, line_width=0,
                      annotation_text="prelim.", annotation_position="top left", annotation_font_size=10)


def stacked_bars(total_by, title, ytitle, scale, colors, labels, hover_fmt, total_line=None, line_name=""):
    """Stacked yearly bars; a year whose parts are not all published is left empty, not shown partly.

    `total_line` (a yearly Series) is drawn over the bars as NASS's published total, so a year whose
    stack is empty still shows the total when NASS publishes one.
    """
    fig = go.Figure()
    for col in total_by.columns:
        fig.add_trace(go.Bar(x=total_by.index, y=total_by[col] / scale, name=labels(col), marker_color=colors.get(col),
                             hovertemplate=f"<b>%{{x}}</b><br>{labels(col)}: %{{y:{hover_fmt}}}<extra></extra>"))
    if total_line is not None:
        fig.add_trace(go.Scatter(x=total_line.index, y=total_line / scale, mode="lines", name=line_name, connectgaps=False,
                                 line=dict(color="#212529", width=2),
                                 hovertemplate=f"<b>%{{x}}</b><br>{line_name}: %{{y:{hover_fmt}}}<extra></extra>"))
    fig.update_layout(barmode="stack", title=title, xaxis_title="Season (end year)", yaxis_title=ytitle,
                      height=430, template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", yanchor="top", y=-0.18))
    _shade_latest(fig)
    return fig


def gap_note(total, scope_label):
    """Sentence naming the years in which a total is left empty because NASS published no value for a part."""
    years = cd.gap_years(total)
    if not years:
        return ""
    return (f"{scope_label} is left empty in {cd.year_ranges(years)}: NASS published no value for at least one fruit "
            "and state that year and no state total either, and a partial total would understate it.")


def _combined_count(measure, frame):
    """NASS values behind a chart drawn from `combined_total`: the fruit rows before NASS's own totals begin and
    those totals from then on, in the years the chart actually draws."""
    years = list(frame.dropna(how="all").index)
    return (cd.count_values(citrus, measure, years=[y for y in years if y < TOTALS_FIRST_YEAR])
            + cd.count_totals(totals, measure, years=years))


def build_acres_by_state():
    return stacked_bars(acres_by_state, "Bearing Acres of Citrus, by State", "Bearing acres (thousands)", 1e3,
                        STATE_COLORS, _state, ",.0f")


def acres_footer():
    return chart_footer(_combined_count("bearing_acres", acres_by_state), [
        "Stacked bars of US bearing acres by state, one bar per season. " + DEF_BEARING,
        PRELIM_NOTE, TOTALS_NOTE, gap_note(acres_by_state, "The acreage total")] + HINTS)


def _value_by_fruit_frame():
    by_fruit = cd.complete_total(citrus, "value_of_production_usd", by="fruit")
    return by_fruit[[f for f in cd.FRUIT_ORDER if f in by_fruit.columns]]


def _adjust(obj, real):
    """Dollar values as reported, or in constant BASE_YEAR dollars."""
    return cd.to_real(obj, FACTORS) if real else obj


def dollar_axis(real):
    return f"Value of production ($ million, {BASE_YEAR} dollars)" if real else "Value of production ($ million, as reported)"


def build_value_by_fruit(real=False):
    return stacked_bars(_adjust(_value_by_fruit_frame(), real), "Value of Production, by Fruit", dollar_axis(real), 1e6,
                        FRUIT_COLORS, lambda f: f, ",.0f", total_line=_adjust(value_total_all, real), line_name="US total")


def value_by_fruit_notes(real=False):
    """Bullets for the value-by-fruit chart: what it shows, why stacks are empty where the line is not, the peak."""
    notes = ["Stacked bars of the value of production by fruit, with the US total as a line. " + DEF_VALUE] + dollar_notes(real)
    if not real:
        notes.append("Because prices rise over time, dollars from different decades should not be compared as if they "
                     "bought the same amount; switch to constant dollars above, or use the share chart.")
    stack_gaps = cd.gap_years(_value_by_fruit_frame())
    if stack_gaps:
        notes.append(f"The fruit stacks are empty in {cd.year_ranges(stack_gaps)}: NASS withheld the value of at least one "
                     "fruit and state, and a partial stack would understate it.")
    notes.append(f"The line is the US total: NASS's published state totals from {TOTALS_FIRST_YEAR} (which include the "
                 f"values withheld at the fruit level) and the sum of the fruit values before that.")
    total = _adjust(value_total_all, real).dropna()
    peak_year, peak = int(total.idxmax()), float(total.max())
    unit = f"{BASE_YEAR} dollars" if real else "dollars as reported"
    peak_note = f"In {unit} the total is highest in {peak_year} (${peak / 1e9:.2f} billion)"
    if peak_year == int(total.index.min()):
        peak_note += ", the first year of the data, so an earlier year could be higher"
    peak_note += f"; in {LATEST_YEAR}{PRELIM_TAG} it is ${total.loc[LATEST_YEAR] / 1e9:.2f} billion, {-cd.pct_change(total.loc[LATEST_YEAR], peak):.0f}% lower."
    notes += [peak_note, gap_note(value_total_all, "The line"), PRELIM_NOTE] + HINTS
    return notes


def value_by_fruit_count():
    """Fruit values in the years the stacks are drawn, plus the NASS state totals behind the line."""
    stack_years = list(_value_by_fruit_frame().dropna(how="all").index)
    return (cd.count_values(citrus, "value_of_production_usd", years=stack_years)
            + cd.count_totals(totals, "value_of_production_usd", years=list(value_total_all.dropna().index)))


def build_value_share_by_state():
    fig = stacked_bars(value_share, "Share of US Citrus Value of Production, by State", "Share of US value (%)", 1,
                       STATE_COLORS, _state, ".0f")
    fig.update_yaxes(range=[0, 100])
    return fig


def share_footer():
    return chart_footer(_combined_count("value_of_production_usd", value_by_state), [
        "Stacked bars of each state's share of the US value of production, one bar per season, so the bars compare "
        "states with each other and are not affected by inflation. " + DEF_VALUE,
        PRELIM_NOTE, TOTALS_NOTE, gap_note(value_by_state, "The value total")] + HINTS)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
METRICS = {
    "bearing_acres": ("Bearing acres", ",.0f"),
    "yield_boxes_per_acre": ("Yield (boxes per acre)", ",.0f"),
    "yield_pct_of_peak": ("Yield, % of each state's own peak", ".0f"),
    "production_boxes": ("Utilized production (million boxes)", ",.1f"),
    "value_of_production_usd": ("Value of production ($ million)", ",.0f"),
    "price_usd_per_box": ("Price per box ($, packinghouse-door)", ",.2f"),
}
METRIC_DEFS = {"bearing_acres": DEF_BEARING, "yield_boxes_per_acre": DEF_YIELD, "yield_pct_of_peak": DEF_YIELD +
               " Each state's line is divided by that state's own highest yield, so states with different box weights compare.",
               "production_boxes": DEF_UTILIZED, "value_of_production_usd": DEF_VALUE, "price_usd_per_box": DEF_PRICE}


def metric_label(metric, real):
    """Axis and title label for a measure; the dollar measures say which dollars."""
    label = METRICS[metric][0]
    if metric not in DOLLAR_METRICS:
        return label
    which = f"{BASE_YEAR} dollars" if real else "as reported"
    return label[:-1] + f", {which})"


FRUITS = [f for f in cd.FRUIT_ORDER if f in set(citrus["fruit"])]
STATES = [s for s in cd.STATE_NAMES if s in set(citrus["state"])]

app.layout = html.Div([
    html.Div([
        html.H1("US Citrus Industry: Acreage, Yield and Value by State", style={
            'color': COLORS['primary'], 'marginBottom': '10px', 'fontSize': '32px', 'fontWeight': 'bold'}),
        html.P("How has the US citrus industry changed since 1990, and which states account for the change?",
               style={'color': '#333', 'margin': '0 0 6px', 'fontSize': '16px'}),
        html.P("For anyone following US agriculture, including analysts and students. Real USDA NASS "
               "data; descriptive only, with no model or forecast.",
               style={'color': '#666', 'marginTop': '0', 'fontSize': '14px'}),
        html.Div([
            html.Label("Dollar values:", style={'fontWeight': 'bold', 'marginRight': '12px'}),
            dcc.RadioItems(id='dollars', value='real', inline=True,
                           options=[{'label': f"Constant {BASE_YEAR} dollars (inflation-adjusted)", 'value': 'real'},
                                    {'label': "As reported by NASS (nominal)", 'value': 'nominal'}],
                           inputStyle={'marginRight': '5px', 'marginLeft': '15px'}),
            html.Span("Applies to the value and price charts; acreage and shares are not affected.",
                      style={'color': '#888', 'fontSize': '12px', 'marginLeft': '15px'}),
        ], style={'display': 'flex', 'alignItems': 'center', 'flexWrap': 'wrap', 'marginTop': '10px'}),
        html.P(SOURCE_NOTICE, id='source-notice', style={'color': '#888', 'fontSize': '12px', 'margin': '12px 0 0'}),
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
                        f"changes are measured from each total's own peak. Totals use NASS's own published state totals "
                        f"from {TOTALS_FIRST_YEAR} and, before that, the sum of the fruit values, which is left blank in a year "
                        f"when a value is missing."), style={'fontSize': '12px', 'color': '#888', 'marginBottom': '20px'}),
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

                html.Div([dcc.Graph(figure=build_acres_by_state()), acres_footer()], style=CARD_STYLE),
                html.Div([dcc.Graph(figure=build_value_share_by_state()), share_footer()], style=CARD_STYLE),
                html.Div([dcc.Graph(id='value-fruit-chart'), html.Div(id='value-fruit-notes')],
                         style={**CARD_STYLE, 'marginBottom': '0'}),
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
                html.Div([dcc.Graph(id='fruit-chart'), html.Div(id='fruit-notes')], style=CARD_STYLE),
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
                html.Div([dcc.Graph(id='state-acres-chart'), html.Div(id='state-acres-note')], style=CARD_STYLE),
                html.Div([dcc.Graph(id='state-value-chart'), html.Div(id='state-value-note')], style=CARD_STYLE),
            ], style={'padding': '20px'})
        ]),

    ])
], style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'})


# ---------------------------------------------------------------------------
# Callbacks: By Fruit
# ---------------------------------------------------------------------------
def _fruit_series(fruit, metric, real=False):
    """Per-state series for one fruit and measure, as {state: DataFrame(year, value, status)}.

    The dollar measures are in constant BASE_YEAR dollars when `real` is set."""
    base = "yield_boxes_per_acre" if metric == "yield_pct_of_peak" else metric
    d = citrus_plot[(citrus_plot["fruit"] == fruit) & (citrus_plot["measure"] == base)]
    out = {}
    for st, g in d.groupby("state"):
        g = g.sort_values("year").copy()
        if metric == "yield_pct_of_peak":
            g["value"] = g["value"] / g["value"].max() * 100
        elif metric in ("production_boxes", "value_of_production_usd"):
            g["value"] = g["value"] / 1e6
        if real and metric in DOLLAR_METRICS:
            g["value"] = g["value"] * g["year"].map(FACTORS)
        out[st] = g
    return out


def _fruit_notes(fruit, metric, real=False):
    """Bullets for a By Fruit chart: what it shows, which values are missing or left out, and why."""
    base = "yield_boxes_per_acre" if metric == "yield_pct_of_peak" else metric
    notes = [f"One line per state that grows {fruit.lower()}, one point per season. {METRIC_DEFS[metric]}"]
    if metric in DOLLAR_METRICS:
        notes += dollar_notes(real)
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
    return notes + HINTS


@app.callback(
    [Output('fruit-chart', 'figure'), Output('fruit-notes', 'children')],
    [Input('fruit-dropdown', 'value'), Input('metric-dropdown', 'value'), Input('dollars', 'value')]
)
def update_fruit(fruit, metric, dollars="real"):
    real = dollars == "real"
    label, fmt = metric_label(metric, real), METRICS[metric][1]
    fig, n = go.Figure(), 0
    for st, g in _fruit_series(fruit, metric, real).items():
        n += int(g["value"].notna().sum())
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
    return fig, chart_footer(n, _fruit_notes(fruit, metric, real))


# ---------------------------------------------------------------------------
# Callbacks: By State
# ---------------------------------------------------------------------------
def _state_stack(state, measure, scale, ytitle, title, hover_fmt, lead_notes, real=False):
    by_fruit = cd.complete_total(citrus, measure, by="fruit", state=state)
    by_fruit = by_fruit[[f for f in cd.FRUIT_ORDER if f in by_fruit.columns]]
    state_total = cd.combined_total(citrus, totals, measure, state=state)
    n = (cd.count_values(citrus, measure, years=list(by_fruit.dropna(how="all").index), state=state)
         + cd.count_totals(totals, measure, years=list(state_total.dropna().index), state=state))
    if real and measure == "value_of_production_usd":
        by_fruit, state_total = _adjust(by_fruit, True), _adjust(state_total, True)
    fig = stacked_bars(by_fruit, title, ytitle, scale, FRUIT_COLORS, lambda f: f, hover_fmt,
                       total_line=state_total, line_name=f"{_state(state)} total")
    years = cd.incomplete_years(citrus, measure, state)
    notes = list(lead_notes)
    if LATEST_PRELIM:
        notes.append(PRELIM_NOTE)
    if years:
        notes.append(f"The stack is empty in {cd.year_ranges(years)}: NASS withheld or did not publish a value for at "
                     f"least one fruit in {_state(state)}, and a partial stack would understate it.")
    notes.append(f"The line is the {_state(state)} total: NASS's published state total from {TOTALS_FIRST_YEAR} and, "
                 f"before that, the sum of the fruit values.")
    return fig, chart_footer(n, notes + HINTS)


@app.callback(
    [Output('state-acres-chart', 'figure'), Output('state-acres-note', 'children'),
     Output('state-value-chart', 'figure'), Output('state-value-note', 'children')],
    [Input('state-dropdown', 'value'), Input('dollars', 'value')]
)
def update_state(state, dollars="real"):
    real = dollars == "real"
    name = _state(state)
    a_fig, a_note = _state_stack(state, "bearing_acres", 1e3, "Bearing acres (thousands)",
                                 f"{name}: Bearing Acres, by Fruit", ",.1f",
                                 [f"Stacked bars of {name}'s bearing acres by fruit, one bar per season. " + DEF_BEARING])
    v_fig, v_note = _state_stack(state, "value_of_production_usd", 1e6, dollar_axis(real),
                                 f"{name}: Value of Production, by Fruit", ",.0f",
                                 [f"Stacked bars of {name}'s value of production by fruit, one bar per season. " + DEF_VALUE]
                                 + dollar_notes(real), real)
    return a_fig, a_note, v_fig, v_note


# ---------------------------------------------------------------------------
# Callback: Industry Overview value chart (follows the dollar toggle)
# ---------------------------------------------------------------------------
@app.callback(
    [Output('value-fruit-chart', 'figure'), Output('value-fruit-notes', 'children')],
    Input('dollars', 'value')
)
def update_value_by_fruit(dollars="real"):
    real = dollars == "real"
    return build_value_by_fruit(real), chart_footer(value_by_fruit_count(), value_by_fruit_notes(real))


# ---------------------------------------------------------------------------
# Host endpoints: /healthz (liveness) and /debugz (what is running and how much memory it uses)
# ---------------------------------------------------------------------------
def _memory_mb():
    """Resident memory of this process in MB, and what the figure is: current (Linux /proc) or peak (resource)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1), "current resident set (VmRSS)"
    except OSError:
        pass
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss          # kilobytes on Linux, bytes on macOS
        return round(peak / (1024 * 1024 if sys.platform == "darwin" else 1024), 1), "peak resident set (ru_maxrss)"
    except ImportError:
        return None, "not available on this platform"


def _version(package):
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def debug_info():
    memory, memory_kind = _memory_mb()
    return {
        "status": "ok",
        "started_at_utc": STARTED_AT,
        "uptime_seconds": round(time.time() - STARTED),
        "pid": os.getpid(),
        "python": platform.python_version(),
        "memory_mb": memory,
        "memory_kind": memory_kind,
        "packages": {p: _version(p) for p in ("dash", "plotly", "pandas", "numpy", "gunicorn")},
        "data": {"citrus_rows": len(citrus), "totals_rows": len(totals), "cpi_months": len(cpi),
                 "latest_season": LATEST_YEAR, "latest_season_preliminary": LATEST_PRELIM},
    }


# Expose Flask server for Gunicorn (Render, Heroku, etc.)
server = app.server


@server.route("/healthz")
def healthz():
    """Liveness for the host: answers 200 as soon as the app has loaded its data."""
    response = jsonify({"status": "ok"})
    response.headers["Cache-Control"] = "no-store"
    return response


@server.route("/debugz")
def debugz():
    response = jsonify(debug_info())
    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    print("[OK] Starting Dash app at http://127.0.0.1:8050")
    print("Press Ctrl+C to stop.")
    app.run(debug=False, port=8050, host="127.0.0.1")
