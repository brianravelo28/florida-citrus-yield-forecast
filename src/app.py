"""
Plotly Dash app: the US citrus industry by fruit and state (acreage, yield,
price and value of production, 1990-2026), from USDA NASS state surveys.
Descriptive only; no model, no forecast.

Tabs: Industry Overview, By Fruit, By State.
"""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd

try:                                  # gunicorn src.app:server and run_dashboard.py import it as a package
    from src import citrus_data as cd
except ImportError:                   # python src/app.py
    import citrus_data as cd

# ---------------------------------------------------------------------------
# Data (all committed CSVs; see docs/SCHEMA.md)
# ---------------------------------------------------------------------------
citrus = cd.load_citrus("data/citrus_by_state.csv")
totals = cd.load_totals("data/citrus_totals_by_state.csv")      # NASS's own state totals, 2008 on
citrus_plot = cd.blank_conflicts(citrus)          # flagged yields drawn as gaps; the file is untouched
conflicts = cd.yield_conflicts(citrus)
TOTALS_FIRST_YEAR = int(totals["year"].min())

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
VALUE_PEAK_YEAR, VALUE_PEAK = int(value_total.idxmax()), float(value_total.max())
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


TOTALS_NOTE = (f" Totals use NASS's own published state totals from {TOTALS_FIRST_YEAR} and, before that, the sum of "
               "the fruit values (the two agree where both exist; see the Methodology).")


def gap_note(total, scope_label):
    """Sentence naming the years in which a total is left empty because NASS published no value for a part."""
    years = cd.gap_years(total)
    if not years:
        return ""
    return (f" {scope_label} is left empty in {cd.year_ranges(years)}: NASS published no value for at least one fruit "
            "and state that year and no state total either, and a partial total would understate it.")


def build_acres_by_state():
    return stacked_bars(acres_by_state, "Bearing Acres of Citrus, by State", "Bearing acres (thousands)", 1e3,
                        STATE_COLORS, _state, ",.0f")


def _value_by_fruit_frame():
    by_fruit = cd.complete_total(citrus, "value_of_production_usd", by="fruit")
    return by_fruit[[f for f in cd.FRUIT_ORDER if f in by_fruit.columns]]


def build_value_by_fruit():
    return stacked_bars(_value_by_fruit_frame(), "Value of Production, by Fruit",
                        "Value of production ($ million, nominal)", 1e6, FRUIT_COLORS, lambda f: f, ",.0f",
                        total_line=value_total_all, line_name="US total")


def value_by_fruit_note():
    """Footnote for the value-by-fruit chart: why stacks are empty where the total line is not."""
    stack_gaps = cd.gap_years(_value_by_fruit_frame())
    note = ""
    if stack_gaps:
        note = (f" The fruit stacks are empty in {cd.year_ranges(stack_gaps)}: NASS withheld the value of at least one "
                "fruit and state, and a partial stack would understate it.")
    note += (f" The line is the US total: NASS's published state totals from {TOTALS_FIRST_YEAR} (which include the "
             f"values withheld at the fruit level) and the sum of the fruit values before that. The nominal total "
             f"peaked in {VALUE_PEAK_YEAR} at ${VALUE_PEAK / 1e9:.2f} billion.")
    note += gap_note(value_total_all, "The line")
    return note


def build_value_share_by_state():
    fig = stacked_bars(value_share, "Share of US Citrus Value of Production, by State", "Share of US value (%)", 1,
                       STATE_COLORS, _state, ".0f")
    fig.update_yaxes(range=[0, 100])
    return fig


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
        html.P("For anyone following US agriculture, including analysts and students. Real USDA NASS "
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

                html.Div([dcc.Graph(figure=build_acres_by_state()), chart_hint(),
                          html.P(PRELIM_NOTE + TOTALS_NOTE + gap_note(acres_by_state, "The acreage total"),
                                 style=FOOTNOTE_STYLE)], style=CARD_STYLE),
                html.Div([dcc.Graph(figure=build_value_share_by_state()), chart_hint(),
                          html.P("Each bar is the share of that year's US value of production, so it compares states "
                                 "with each other and is not affected by inflation." + TOTALS_NOTE
                                 + gap_note(value_by_state, "The value total"),
                                 style=FOOTNOTE_STYLE)], style=CARD_STYLE),
                html.Div([dcc.Graph(figure=build_value_by_fruit()), chart_hint(),
                          html.P(NOMINAL_NOTE + " Because they are not adjusted, dollar values should not be compared "
                                 "across decades as if they bought the same amount; use the share chart above for that."
                                 + value_by_fruit_note(),
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
    state_total = cd.combined_total(citrus, totals, measure, state=state)
    fig = stacked_bars(by_fruit, title, ytitle, scale, FRUIT_COLORS, lambda f: f, hover_fmt,
                       total_line=state_total, line_name=f"{_state(state)} total")
    years = cd.incomplete_years(citrus, measure, state)
    notes = [note_prefix] if note_prefix else []
    if LATEST_PRELIM:
        notes.append(PRELIM_NOTE)
    if years:
        notes.append(f"The stack is empty in {cd.year_ranges(years)}: NASS withheld or did not publish a value for at "
                     f"least one fruit in {_state(state)}, and a partial stack would understate it.")
    notes.append(f"The line is the {_state(state)} total: NASS's published state total from {TOTALS_FIRST_YEAR} and, "
                 f"before that, the sum of the fruit values.")
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


# Expose Flask server for Gunicorn (Render, Heroku, etc.)
server = app.server

if __name__ == "__main__":
    print("[OK] Starting Dash app at http://127.0.0.1:8050")
    print("Press Ctrl+C to stop.")
    app.run(debug=False, port=8050, host="127.0.0.1")
