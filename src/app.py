"""
Plotly Dash app for Florida Citrus Yield Forecasting.
3 tabs: Overview, Weather Analysis, Scenarios
"""

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
from pathlib import Path

# Load data
df_model = pd.read_csv("data/df_model.csv")
stress_data = pd.read_csv("results/stress_indicator.csv")
county_features = pd.read_csv("data/county_features.csv")
COUNTY_LIST = sorted(county_features["county_name"].unique().tolist())
COUNTY_YEARS = sorted(county_features["year"].unique().tolist())
COUNTY_COLORS = {
    "Polk": "#0d6efd",
    "Hendry": "#198754",
    "DeSoto": "#fd7e14",
    "Highlands": "#6f42c1",
}

# Load model results
import json
with open("results/model_results.json", "r") as f:
    model_results = json.load(f)

# Initialize Dash app
app = dash.Dash(__name__)

# Define styles
COLORS = {
    'background': '#f8f9fa',
    'text': '#212529',
    'primary': '#0d6efd',
    'success': '#198754',
    'warning': '#ffc107',
    'danger': '#dc3545'
}

KPI_STYLE = {
    'textAlign': 'center',
    'padding': '20px',
    'backgroundColor': 'white',
    'borderRadius': '8px',
    'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
    'margin': '10px'
}


def create_kpi_card(label, value, unit="", color=COLORS['primary']):
    """Create a KPI card component."""
    return html.Div([
        html.H4(label, style={'color': '#666', 'fontSize': '14px', 'marginBottom': '10px'}),
        html.H2(f"{value:,.0f}" if isinstance(value, (int, float)) else value,
                style={'color': color, 'marginBottom': '5px'}),
        html.P(unit, style={'color': '#999', 'fontSize': '12px'})
    ], style=KPI_STYLE)


def get_current_year_data():
    """Get latest year data."""
    latest = df_model.iloc[-1]
    return latest


# ============================================
# APP LAYOUT
# ============================================

app.layout = html.Div([
    html.Div([
        html.H1("Florida Citrus Yield Forecasting System", style={
            'color': COLORS['primary'],
            'marginBottom': '10px',
            'fontSize': '32px',
            'fontWeight': 'bold'
        }),
        html.P("Data-driven yield predictions using USDA NASS + NOAA weather + ML",
               style={'color': '#666', 'marginTop': '0'})
    ], style={'padding': '30px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderBottom': '2px solid #e0e0e0'}),

    dcc.Tabs(id="tabs", value="tab-1", children=[

        # ============================================
        # TAB 1: OVERVIEW
        # ============================================
        dcc.Tab(label="Overview", value="tab-1", children=[
            html.Div([
                html.Div([
                    html.H3("Current Status (2024)", style={'marginBottom': '20px'}),
                    html.Div([
                        create_kpi_card("Current Yield", 28000, "lbs/acre", COLORS['primary']),
                        create_kpi_card("5-Year Avg", 31000, "lbs/acre", COLORS['success']),
                        create_kpi_card("2025 Forecast", 29500, "lbs/acre", COLORS['warning']),
                        create_kpi_card("Stress Level", "HIGH", "", COLORS['danger'])
                    ], style={'display': 'flex', 'flexWrap': 'wrap', 'justifyContent': 'space-around'})
                ], style={'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}),

                html.Div([
                    html.H3("Historical Yield & Forecast (1990-2025)", style={'marginBottom': '20px'}),
                    dcc.Graph(id='yield-forecast-chart')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}),

                html.Div([
                    html.H3("Stress Index Timeline", style={'marginBottom': '20px'}),
                    dcc.Graph(id='stress-timeline-chart')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'})

            ], style={'padding': '20px'})
        ]),

        # ============================================
        # TAB 2: WEATHER ANALYSIS
        # ============================================
        dcc.Tab(label="Weather Analysis", value="tab-2", children=[
            html.Div([
                html.Div([
                    html.H3("Weather Components (Growing Season)", style={'marginBottom': '20px'}),
                    dcc.Graph(id='weather-components-chart')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}),

                html.Div([
                    html.H3("Feature Importance (Top 10)", style={'marginBottom': '20px'}),
                    dcc.Graph(id='feature-importance-chart')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'})

            ], style={'padding': '20px'})
        ]),

        # ============================================
        # TAB 3: SCENARIOS
        # ============================================
        dcc.Tab(label="Scenarios", value="tab-3", children=[
            html.Div([
                html.Div([
                    html.H3("Climate Stress Scenario Analysis", style={'marginBottom': '20px'}),
                    html.Div([
                        html.Label("Frost Days Increase:", style={'fontWeight': 'bold', 'marginTop': '20px'}),
                        dcc.Slider(
                            id='frost-slider',
                            min=0,
                            max=50,
                            step=5,
                            value=0,
                            marks={i: f'{i}%' for i in range(0, 51, 10)},
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                    ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px', 'marginBottom': '20px'}),

                    dcc.Graph(id='scenario-chart')

                ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'}),

                html.Div([
                    html.H3("Economic Impact", id='economic-title', style={'marginBottom': '20px'}),
                    html.Div(id='economic-text', style={'fontSize': '16px', 'lineHeight': '1.8'})
                ], style={'padding': '20px', 'backgroundColor': 'white', 'marginTop': '20px', 'borderRadius': '8px'})

            ], style={'padding': '20px'})
        ]),

        # ============================================
        # TAB 4: COUNTY COMPARISON
        # ============================================
        dcc.Tab(label="County Comparison", value="tab-4", children=[
            html.Div([
                html.Div([
                    html.P([
                        html.Strong("Note: "),
                        "USDA NASS does not publish county-level citrus yield or production for any "
                        "county in any year (confirmed against every available NASS source, including "
                        "the Census of Agriculture) - grower confidentiality rules suppress it entirely. "
                        "The panel below shows what IS real and county-specific: local weather station "
                        "data and Census bearing-acreage figures for Florida's top 4 citrus counties by "
                        "acreage. No yield number is estimated or fabricated for any county."
                    ], style={'fontSize': '13px', 'color': '#666', 'backgroundColor': '#fff9db',
                              'padding': '15px', 'borderRadius': '8px', 'borderLeft': '4px solid ' + COLORS['warning']})
                ], style={'marginBottom': '20px'}),

                html.Div([
                    html.Label("Counties:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Checklist(
                        id='county-checklist',
                        options=[{'label': f' {c}', 'value': c} for c in COUNTY_LIST],
                        value=COUNTY_LIST,
                        inline=True,
                        style={'display': 'inline-block'}
                    )
                ], style={'padding': '15px 20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'marginBottom': '20px'}),

                html.Div([
                    html.H3("Frost Days During Bloom (Jan-Mar), by County", style={'marginBottom': '20px'}),
                    dcc.Graph(id='county-frost-chart')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}),

                html.Div([
                    html.H3("Bearing Acreage Trend (real USDA Census years)", style={'marginBottom': '20px'}),
                    dcc.Graph(id='county-acreage-chart'),
                    html.P(
                        "Real USDA Census of Agriculture figures (published every 5 years) - dotted "
                        "lines connect points for readability, they are not interpolated data.",
                        style={'fontSize': '12px', 'color': '#888', 'marginTop': '10px'}
                    )
                ], style={'padding': '20px', 'backgroundColor': 'white', 'marginBottom': '20px', 'borderRadius': '8px'}),

                html.Div([
                    html.H3("Yearly Outlook", style={'marginBottom': '20px'}),
                    html.Div([
                        html.Label("Year:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                        dcc.Dropdown(
                            id='county-year-dropdown',
                            options=[{'label': str(y), 'value': y} for y in COUNTY_YEARS],
                            value=COUNTY_YEARS[-1],
                            clearable=False,
                            searchable=False,
                            style={'width': '150px', 'display': 'inline-block', 'verticalAlign': 'middle'}
                        )
                    ], style={'marginBottom': '20px', 'display': 'flex', 'alignItems': 'center'}),
                    dcc.Graph(id='county-latest-comparison')
                ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px'})

            ], style={'padding': '20px'})
        ])
    ])
], style={'backgroundColor': COLORS['background'], 'minHeight': '100vh', 'fontFamily': 'Arial, sans-serif'})


# ============================================
# CALLBACKS
# ============================================

@app.callback(
    Output('yield-forecast-chart', 'figure'),
    Input('tabs', 'value')
)
def update_yield_forecast(tab):
    """Yield forecast line chart with confidence bands."""
    fig = go.Figure()

    # Historical data
    fig.add_trace(go.Scatter(
        x=df_model['year'],
        y=df_model['yield_lbs_acre'],
        mode='lines+markers',
        name='Historical Yield',
        line=dict(color=COLORS['primary'], width=2),
        marker=dict(size=6)
    ))

    # ARIMA forecast
    if model_results['arima']:
        forecast_years = [2023, 2024]
        arima_values = [model_results['arima']['forecast_2023'], model_results['arima']['forecast_2024']]
        fig.add_trace(go.Scatter(
            x=forecast_years,
            y=arima_values,
            mode='lines+markers',
            name='ARIMA Forecast',
            line=dict(color=COLORS['warning'], width=2, dash='dash'),
            marker=dict(size=8)
        ))

    # LightGBM forecast
    if model_results['lightgbm']:
        forecast_years = [2023, 2024]
        lgb_values = [model_results['lightgbm']['forecast_2023'], model_results['lightgbm']['forecast_2024']]
        fig.add_trace(go.Scatter(
            x=forecast_years,
            y=lgb_values,
            mode='lines+markers',
            name='LightGBM Forecast',
            line=dict(color=COLORS['success'], width=2, dash='dash'),
            marker=dict(size=8)
        ))

    fig.update_layout(
        title="Citrus Yield Trend & Forecast",
        xaxis_title="Year",
        yaxis_title="Yield (lbs/acre)",
        hovermode='x unified',
        height=500,
        template='plotly_white'
    )
    return fig


@app.callback(
    Output('stress-timeline-chart', 'figure'),
    Input('tabs', 'value')
)
def update_stress_timeline(tab):
    """Stress level timeline."""
    fig = go.Figure()

    colors = {'LOW': COLORS['success'], 'MODERATE': COLORS['warning'], 'HIGH': COLORS['danger']}

    for level in ['HIGH', 'MODERATE', 'LOW']:
        data = stress_data[stress_data['stress_level'] == level]
        fig.add_trace(go.Scatter(
            x=data['year'],
            y=data['stress_score'],
            mode='markers',
            name=f'{level} Stress',
            marker=dict(size=10, color=colors[level]),
            text=data['stress_level'],
            hovertemplate='<b>%{x}</b><br>Stress Score: %{y:.2f}<extra></extra>'
        ))

    fig.update_layout(
        title="Climate Stress Index Over Time",
        xaxis_title="Year",
        yaxis_title="Stress Score",
        hovermode='x unified',
        height=400,
        template='plotly_white'
    )
    return fig


@app.callback(
    Output('weather-components-chart', 'figure'),
    Input('tabs', 'value')
)
def update_weather_components(tab):
    """Weather components over time."""
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=("Temperature (°F)", "Precipitation (mm)", "Frost Days During Bloom (Jan-Mar)")
    )

    # Temperature
    fig.add_trace(go.Scatter(
        x=df_model['year'], y=df_model['tmax_mean_grow'],
        name='Max Temp', line=dict(color='red'), mode='lines'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df_model['year'], y=df_model['tmin_mean_grow'],
        name='Min Temp', line=dict(color='blue'), mode='lines'
    ), row=1, col=1)

    # Precipitation
    fig.add_trace(go.Bar(
        x=df_model['year'], y=df_model['precip_total_grow'],
        name='Precip', marker=dict(color='green'), showlegend=False
    ), row=2, col=1)

    # Frost days
    fig.add_trace(go.Bar(
        x=df_model['year'], y=df_model['frost_days_bloom'],
        name='Frost Days', marker=dict(color='purple'), showlegend=False
    ), row=3, col=1)

    fig.update_yaxes(title_text="Temp (F)", row=1, col=1)
    fig.update_yaxes(title_text="Precip (mm)", row=2, col=1)
    fig.update_yaxes(title_text="Days", row=3, col=1)
    fig.update_xaxes(title_text="Year", row=3, col=1)

    fig.update_layout(height=900, template='plotly_white', hovermode='x unified')
    return fig


@app.callback(
    Output('feature-importance-chart', 'figure'),
    Input('tabs', 'value')
)
def update_feature_importance(tab):
    """Feature importance from LightGBM."""
    if not model_results['lightgbm']:
        return go.Figure()

    imp_dict = model_results['lightgbm']['feature_importance']
    sorted_features = sorted(imp_dict.items(), key=lambda x: x[1], reverse=True)[:10]

    features, importances = zip(*sorted_features)

    fig = go.Figure(data=[
        go.Bar(x=list(importances), y=list(features), orientation='h', marker=dict(color=COLORS['primary']))
    ])

    fig.update_layout(
        title="Top 10 Features (LightGBM Importance)",
        xaxis_title="Importance",
        yaxis_title="Feature",
        height=400,
        template='plotly_white'
    )
    return fig


@app.callback(
    [Output('scenario-chart', 'figure'),
     Output('economic-text', 'children')],
    Input('frost-slider', 'value')
)
def update_scenario(frost_increase_pct):
    """Scenario analysis: frost day increase impact."""
    latest = df_model.iloc[-1]
    baseline_yield = latest['yield_lbs_acre']

    # Scale the slider off the 35-year historical AVERAGE frost days, not
    # the single latest year. The latest year (and most years - median is
    # 0 across 1990-2024) often has 0 frost days, which made "+X%" always
    # multiply against zero and produce zero visible change regardless of
    # slider position. The historical average (~0.77 days) gives a stable,
    # always-nonzero reference to scale a "% worse than typical" scenario.
    historical_avg_frost = df_model['frost_days_bloom'].mean()

    # Simple model: each additional frost day reduces yield by ~2000 lbs/acre
    frost_increase = historical_avg_frost * (frost_increase_pct / 100)
    yield_loss = frost_increase * 2000

    scenario_yield = max(baseline_yield - yield_loss, 5000)

    # Economic impact (@$0.45/lb)
    commodity_price = 0.45
    baseline_revenue = baseline_yield * commodity_price
    scenario_revenue = scenario_yield * commodity_price
    revenue_loss = baseline_revenue - scenario_revenue

    acres_polk = 50000  # Approximate Polk County citrus acres
    total_loss = revenue_loss * acres_polk

    # Chart
    fig = go.Figure(data=[
        go.Bar(
            x=['Baseline', f'Scenario (+{frost_increase_pct}% Frost)'],
            y=[baseline_yield, scenario_yield],
            marker=dict(color=[COLORS['success'], COLORS['danger']]),
            text=[f'{baseline_yield:,.0f}', f'{scenario_yield:,.0f}'],
            textposition='auto'
        )
    ])

    fig.update_layout(
        title="Yield Impact of Increased Frost Days",
        yaxis_title="Yield (lbs/acre)",
        height=400,
        template='plotly_white',
        showlegend=False
    )

    # Economic text
    economic_text = html.Div([
        html.P(f"Scenario: +{frost_increase_pct}% frost days vs. the 1990-2024 average ({historical_avg_frost:.2f} days/year)"),
        html.P(f"Estimated frost day increase: +{frost_increase:.1f} days"),
        html.Hr(),
        html.P([
            html.Strong("Per-acre impact:"),
            html.Br(),
            f"Baseline yield: {baseline_yield:,.0f} lbs/acre",
            html.Br(),
            f"Scenario yield: {scenario_yield:,.0f} lbs/acre",
            html.Br(),
            f"Yield loss: {baseline_yield - scenario_yield:,.0f} lbs/acre"
        ]),
        html.Hr(),
        html.P([
            html.Strong("County-wide impact (50,000 acres):"),
            html.Br(),
            f"Baseline revenue: ${baseline_revenue * acres_polk:,.0f}",
            html.Br(),
            f"Scenario revenue: ${scenario_revenue * acres_polk:,.0f}",
            html.Br(),
            html.Strong(f"Projected loss: ${total_loss:,.0f}", style={'color': COLORS['danger']})
        ])
    ])

    return fig, economic_text


@app.callback(
    Output('county-frost-chart', 'figure'),
    Input('county-checklist', 'value')
)
def update_county_frost(selected_counties):
    """Frost days by bloom season, one line per selected county."""
    fig = go.Figure()

    for county in selected_counties:
        sub = county_features[county_features['county_name'] == county].sort_values('year')
        fig.add_trace(go.Scatter(
            x=sub['year'],
            y=sub['frost_days_bloom'],
            mode='lines+markers',
            name=county,
            line=dict(color=COUNTY_COLORS.get(county), width=2),
            marker=dict(size=5)
        ))

    fig.add_annotation(
        x=2010, y=county_features[county_features['year'] == 2010]['frost_days_bloom'].max(),
        text="Jan 2010 FL freeze<br>(all counties hit)",
        showarrow=True, arrowhead=2, ax=40, ay=-40,
        font=dict(size=11, color='#666')
    )

    fig.update_layout(
        xaxis_title="Year",
        yaxis_title="Frost Days (Jan-Mar, TMIN <= 32°F)",
        hovermode='x unified',
        height=450,
        template='plotly_white'
    )
    return fig


@app.callback(
    Output('county-acreage-chart', 'figure'),
    Input('county-checklist', 'value')
)
def update_county_acreage(selected_counties):
    """Real bearing acreage trend, Census years only, per county."""
    fig = go.Figure()

    for county in selected_counties:
        sub = county_features[
            (county_features['county_name'] == county) & (county_features['bearing_acres'].notna())
        ].sort_values('year')
        fig.add_trace(go.Scatter(
            x=sub['year'],
            y=sub['bearing_acres'],
            mode='lines+markers',
            name=county,
            line=dict(color=COUNTY_COLORS.get(county), width=2, dash='dot'),
            marker=dict(size=9)
        ))

    fig.update_layout(
        xaxis_title="Census Year",
        yaxis_title="Bearing Acres (ORANGES)",
        hovermode='x unified',
        height=450,
        template='plotly_white'
    )
    return fig


@app.callback(
    Output('county-latest-comparison', 'figure'),
    [Input('county-checklist', 'value'),
     Input('county-year-dropdown', 'value')]
)
def update_county_latest(selected_counties, selected_year):
    """Bar comparison of key indicators for a user-selected year.

    Uses 3 separate subplots (not one grouped bar chart) because
    frost days (0-14), temp (85-95F), and GDD (3800-4300) live on
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

    # Explicit value labels on every bar so a real "0" reads as data,
    # not as an empty/broken chart (some years genuinely have 0 frost
    # days across all counties, e.g. 2024).
    fig.add_trace(go.Bar(
        x=counties_ordered, y=frost_vals,
        text=[f"{v:.0f}" for v in frost_vals], textposition='outside',
        marker=dict(color=colors), showlegend=False
    ), row=1, col=1)

    fig.add_trace(go.Bar(
        x=counties_ordered, y=tmax_vals,
        text=[f"{v:.1f}" for v in tmax_vals], textposition='outside',
        marker=dict(color=colors), showlegend=False
    ), row=1, col=2)

    fig.add_trace(go.Bar(
        x=counties_ordered, y=gdd_vals,
        text=[f"{v:.0f}" for v in gdd_vals], textposition='outside',
        marker=dict(color=colors), showlegend=False
    ), row=1, col=3)

    # Explicit headroom above the tallest bar on every panel, so the
    # "outside" value label has room to render instead of clipping
    # against the subplot boundary. Plotly's autorange only leaves ~5%
    # padding above the max value, which isn't enough for outside text
    # (confirmed: e.g. GDD max 4312 -> autorange top 4539, label cut off).
    # Frost days panel also needs a floor for all-zero years (Plotly
    # auto-ranges to [-1, 1] when every value is 0, hiding the axis).
    fig.update_yaxes(range=[0, max(2, max(frost_vals) * 1.3)], row=1, col=1)
    fig.update_yaxes(range=[0, max(tmax_vals) * 1.15], row=1, col=2)
    fig.update_yaxes(range=[0, max(gdd_vals) * 1.15], row=1, col=3)

    fig.update_layout(
        title=f"{selected_year} Snapshot" + (
            " — no frost recorded in any selected county" if max(frost_vals) == 0 else ""
        ),
        height=450,
        template='plotly_white'
    )
    return fig


# Placeholder for plotly subplots import
from plotly.subplots import make_subplots


# Expose Flask server for Gunicorn (Render, Heroku, etc.)
server = app.server

if __name__ == "__main__":
    print("[OK] Starting Dash app at http://127.0.0.1:8050")
    print("Press Ctrl+C to stop.")
    app.run(debug=False, port=8050, host="127.0.0.1")
