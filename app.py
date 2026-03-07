# Importing the libraries.

# tools
import os
import gc
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# dash & dash components
import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc

# plotly
import plotly.express as px
import plotly.graph_objs as go
from dash.dependencies import Input, Output

# data handling
import pandas as pd
import polars as pl

# dates
from datetime import date


def load_data():
    """
    Downloads the OWID COVID dataset, selects only the needed columns,
    filters to 2020-2022, normalizes units, and returns a lean Pandas DataFrame.
    Memory strategy:
      - Select columns in Polars BEFORE converting to Pandas (avoids a full Pandas copy).
      - Delete the CSV from disk immediately after reading.
      - Call gc.collect() after every heavyweight step.
    """

    # OWID covid Dataset URL
    url = (
        'https://raw.githubusercontent.com/owid/covid-19-data/master/'
        'public/data/owid-covid-data.csv'
    )

    # Fetch with retry logic (3 attempts, exponential back-off)
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    response = session.get(url, timeout=30)
    response.raise_for_status()

    csv_path = 'owid-covid-data.csv'
    with open(csv_path, 'wb') as f:
        f.write(response.content)

    # Free the HTTP response bytes immediately
    del response
    gc.collect()

    # ------------------------------------------------------------------ #
    # Read ONLY the columns we actually need (Polars lazy makes this cheap)
    # ------------------------------------------------------------------ #
    use_cols = [
        'iso_code', 'continent', 'location', 'date',
        'total_deaths', 'total_cases',
        'new_cases_per_million', 'new_deaths_per_million',
        'total_tests_per_thousand', 'new_tests_per_thousand',
        'hospital_beds_per_thousand',
        'total_vaccinations_per_hundred',
        'people_vaccinated_per_hundred',
        'people_fully_vaccinated_per_hundred',
        'total_boosters_per_hundred',
    ]

    data = (
        pl.scan_csv(csv_path)          # lazy – no full file in RAM yet
          .select(use_cols)
          .collect()
    )

    # Delete the CSV from disk right away
    os.remove(csv_path)
    gc.collect()

    # Parse date and extract year
    data = data.with_columns(
        pl.col('date').str.strptime(pl.Date, strict=False)
    )
    data = data.with_columns(
        pl.col('date').dt.year().alias('year')
    )

    # Filter to 2020-2022 only (drops a big chunk of rows)
    data = data.filter(pl.col('year').is_in([2020, 2021, 2022]))

    # Normalize units – keep everything as Float32 to halve memory vs Float64
    data = data.with_columns([
        pl.col('new_cases_per_million').cast(pl.Float32, strict=False),
        pl.col('new_deaths_per_million').cast(pl.Float32, strict=False),
        (pl.col('total_tests_per_thousand').cast(pl.Float32, strict=False) * 1000).alias('total_tests_per_million'),
        (pl.col('new_tests_per_thousand').cast(pl.Float32, strict=False) * 1000).alias('new_tests_per_million'),
        (pl.col('hospital_beds_per_thousand').cast(pl.Float32, strict=False) * 1000).alias('hospital_beds_per_million'),
        (pl.col('total_vaccinations_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('total_vaccinations_per_million'),
        (pl.col('people_vaccinated_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('people_vaccinated_per_million'),
        (pl.col('people_fully_vaccinated_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('people_fully_vaccinated_per_million'),
        (pl.col('total_boosters_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('total_boosters_per_million'),
        pl.col('total_deaths').cast(pl.Float32, strict=False),
        pl.col('total_cases').cast(pl.Float32, strict=False),
    ])

    final_cols = [
        'iso_code', 'continent', 'location', 'date',
        'total_deaths', 'total_cases',
        'new_cases_per_million', 'new_deaths_per_million',
        'total_tests_per_million', 'new_tests_per_million',
        'hospital_beds_per_million',
        'total_vaccinations_per_million',
        'people_vaccinated_per_million',
        'people_fully_vaccinated_per_million',
        'total_boosters_per_million',
    ]

    # Convert to Pandas once, as a lean categorical/downcasted frame
    df = data.select(final_cols).to_pandas()

    # Free Polars frame
    del data
    gc.collect()

    # Convert object columns to category to save RAM
    for col in ['iso_code', 'continent', 'location']:
        df[col] = df[col].astype('category')

    # date column: keep as Pandas datetime
    df['date'] = pd.to_datetime(df['date'])

    return df


# ---------------------------------------------------------------------------
# Load data ONCE at startup
# ---------------------------------------------------------------------------
data = load_data()

# ---------------------------------------------------------------------------
# Pre-split the DataFrame by continent so callbacks never touch the full frame
# ---------------------------------------------------------------------------
continents = data['continent'].dropna().unique().tolist()
data_by_continent = {
    c: data[data['continent'] == c].reset_index(drop=True)
    for c in continents
}
# Drop the full frame – we only need the per-continent slices
del data
gc.collect()

select_continent = {c: c for c in continents}

# Shared min/max date across all continents (needed for DatePickerRange)
global_min_date = min(df['date'].min() for df in data_by_continent.values())
global_max_date = max(df['date'].max() for df in data_by_continent.values())

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    meta_tags=[{
        'name': 'viewport',
        'content': 'width=device-width, initial-scale=0.6, maximum-scale=.9, minimum-scale=0.5',
    }]
)
server = app.server

app.layout = dbc.Container([

    dbc.Row([
        dbc.Col(html.H3("COVID-19 🦠 Tracker", className='header-title text-center mt-4 mb-2'), width=4),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Dropdown(
                        id="continent-dropdown",
                        options=[{"label": v, "value": k} for k, v in select_continent.items()],
                        value="Africa",
                        clearable=False,
                        style={'borderRadius': '5px', 'width': '100%', 'verticalAlign': "middle"},
                        className="ml-2",
                    ),
                ], style={"width": "100%"})
            ], className="dropdown-card main-navigation m-1"),
        ], width={'size': 4}),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.DatePickerRange(
                        id='my-date-picker-range',
                        min_date_allowed=global_min_date,
                        max_date_allowed=global_max_date,
                        initial_visible_month=global_min_date,
                        start_date=global_min_date,
                        end_date=global_max_date,
                        style={'borderRadius': '5px', 'width': 'auto', 'verticalAlign': "middle"}
                    ),
                ], style={"width": "100%"})
            ], className="dropdown-card text-center m-1"),
        ], width={'size': 4}),
    ]),

    dbc.Row([
        dbc.Col([dbc.Card([dbc.CardBody([
            html.Span("Confirmed cases per million", className="card-text text-center"),
            html.H3(style={"color": "#389fd6"}, id="casos-confirmados-text"),
            html.H5(id="nuevos-casos-text", children="0"),
        ])])], width=4),

        dbc.Col([dbc.Card([dbc.CardBody([
            html.Span("Confirmed deaths per million", className="card-text text-center"),
            html.H3(style={"color": "#df2935"}, id="muertes-confirmadas-text"),
            html.H5(id="muertes-text", children="0"),
        ])])], width=4),

        dbc.Col([dbc.Card([dbc.CardBody([
            html.Span("Mortality rate %", className="card-text text-center"),
            html.H3(style={"color": "#adfc92"}, id="mortality-rate-text"),
            html.H5(id="mortalidad-text", children="0"),
        ])])], width=4),
    ]),

    dbc.Row([
        dbc.Col([dbc.Card([dbc.CardBody([dcc.Graph(id='pie-plot', figure={})])])], width=4, className="mt-1"),
        dbc.Col([dbc.Card([dbc.CardBody([dcc.Graph(id='hist1-plot', figure={})])])], width=4, className="mt-1"),
        dbc.Col([dbc.Card([dbc.CardBody([dcc.Graph(id='hist2-plot', figure={})])])], width=4, className="mt-1"),
    ]),

    dbc.Row([
        dbc.Col([dbc.Card([dbc.CardBody([dcc.Graph(id='line-plot', figure={})])])], width=12, className="mt-1"),
    ]),

], fluid=True)


# ---------------------------------------------------------------------------
# Helper: return the slice for a continent filtered by date range
# ---------------------------------------------------------------------------
def get_slice(continent, start_date, end_date):
    """
    Returns a VIEW (not a copy) of the pre-split continent DataFrame
    filtered to the requested date range.
    """
    df = data_by_continent.get(continent)
    if df is None:
        return pd.DataFrame()
    mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
    return df.loc[mask]   # loc returns a view, not a copy


# ---------------------------------------------------------------------------
# Shared layout helpers
# ---------------------------------------------------------------------------
_LAYOUT_BASE = dict(
    plot_bgcolor='#000000',
    paper_bgcolor='#000000',
    title=dict(y=0.9, x=0.5, yanchor='top', xanchor='center'),
    title_font=dict(size=25, color='#8a8d93', family="Lato, sans-serif"),
    font=dict(color='#8a8d93'),
    hoverlabel=dict(bgcolor="#c6ccd8", font_size=13, font_family="Lato, sans-serif"),
)


# ---------------------------------------------------------------------------
# Callback: KPI cards
# ---------------------------------------------------------------------------
@app.callback(
    Output('nuevos-casos-text', 'children'),
    Output('muertes-text', 'children'),
    Output('mortalidad-text', 'children'),
    Input('continent-dropdown', 'value'),
    Input('my-date-picker-range', 'start_date'),
    Input('my-date-picker-range', 'end_date'),
)
def display_status(continent, start_date, end_date):
    dfq = get_slice(continent, start_date, end_date)
    if dfq.empty:
        return 0, 0, 0

    last_day = dfq[dfq['date'] == dfq['date'].max()]
    total_cases_sum   = last_day['total_cases'].sum()
    total_deaths_sum  = last_day['total_deaths'].sum()

    casos_acumulados  = round(float(total_cases_sum) / 1_000_000, 2)
    muertes_acumulado = round(float(total_deaths_sum) / 1_000_000, 2)
    mortality_rate    = round(float(total_deaths_sum / total_cases_sum * 100) if total_cases_sum > 0 else 0.0, 2)

    return casos_acumulados, muertes_acumulado, mortality_rate


# ---------------------------------------------------------------------------
# Callback: Pie chart
# ---------------------------------------------------------------------------
@app.callback(
    Output('pie-plot', 'figure'),
    Input('continent-dropdown', 'value'),
    Input('my-date-picker-range', 'start_date'),
    Input('my-date-picker-range', 'end_date'),
)
def update_pie(continent, start_date, end_date):
    df1 = get_slice(continent, start_date, end_date)

    agg = (
        df1.groupby('location', observed=True)['new_cases_per_million']
           .mean()
           .sort_values(ascending=False)
           .head(10)
    )

    fig = px.pie(
        agg,
        names=agg.index,
        values=agg.values,
        hole=0.7,
        title='New cases per million',
    )
    fig.update_traces(hovertemplate=None, textposition='inside', textinfo='percent+label', rotation=45)
    fig.update_layout(showlegend=False, **_LAYOUT_BASE)
    return fig


# ---------------------------------------------------------------------------
# Callback: Hist 1 – fully vaccinated
# ---------------------------------------------------------------------------
@app.callback(
    Output('hist1-plot', 'figure'),
    Input('continent-dropdown', 'value'),
    Input('my-date-picker-range', 'start_date'),
    Input('my-date-picker-range', 'end_date'),
)
def update_hist1(continent, start_date, end_date):
    df2 = get_slice(continent, start_date, end_date)

    fig = px.histogram(
        df2,
        y='location',
        x=df2.groupby('location', observed=True)['people_fully_vaccinated_per_million']
             .transform(lambda s: s.rolling(7).mean()),
        color='location',
        color_discrete_sequence=px.colors.qualitative.Plotly,
        labels={'location': 'Country', 'people_fully_vaccinated_per_million': 'Fully vaccinated per million'},
        title='Fully vaccinated per million',
    )
    fig.update_yaxes(showgrid=False, ticksuffix=' ', showline=False, categoryorder='total ascending')
    fig.update_xaxes(visible=True)
    fig.update_layout(
        margin=dict(t=100, b=10, l=70, r=40),
        showlegend=False,
        hovermode="y unified",
        xaxis_title=" ", yaxis_title=" ",
        **_LAYOUT_BASE,
    )
    return fig


# ---------------------------------------------------------------------------
# Callback: Hist 2 – deaths per million
# ---------------------------------------------------------------------------
@app.callback(
    Output('hist2-plot', 'figure'),
    Input('continent-dropdown', 'value'),
    Input('my-date-picker-range', 'start_date'),
    Input('my-date-picker-range', 'end_date'),
)
def update_hist2(continent, start_date, end_date):
    df3 = get_slice(continent, start_date, end_date)

    fig = px.histogram(
        df3,
        y='location',
        x='new_deaths_per_million',
        color='location',
        color_discrete_sequence=px.colors.qualitative.Plotly,
        labels={'location': 'Country', 'new_deaths_per_million': 'Deaths per million'},
        title='Deaths per million',
    )
    fig.update_yaxes(showgrid=False, ticksuffix=' ', showline=False, categoryorder='total ascending')
    fig.update_xaxes(visible=True)
    fig.update_layout(
        margin=dict(t=100, b=10, l=70, r=40),
        showlegend=False,
        hovermode="y unified",
        xaxis_title=" ", yaxis_title=" ",
        **_LAYOUT_BASE,
    )
    return fig


# ---------------------------------------------------------------------------
# Callback: Area – weekly deaths
# ---------------------------------------------------------------------------
@app.callback(
    Output('line-plot', 'figure'),
    Input('continent-dropdown', 'value'),
    Input('my-date-picker-range', 'start_date'),
    Input('my-date-picker-range', 'end_date'),
)
def update_line(continent, start_date, end_date):
    df4 = get_slice(continent, start_date, end_date)

    fig = px.area(
        df4,
        x='date',
        y=df4.groupby('location', observed=True)['new_deaths_per_million']
             .transform(lambda s: s.rolling(7).mean()),
        color='location',
        color_discrete_sequence=px.colors.qualitative.Plotly,
        labels={'location': 'Country', 'new_deaths_per_million': 'Deaths per million'},
        title='Weekly deaths per million',
    )
    fig.update_yaxes(showgrid=False, ticksuffix=' ', showline=False, categoryorder='total ascending')
    fig.update_xaxes(visible=False)
    fig.update_layout(
        margin=dict(t=100, b=10, l=70, r=40),
        showlegend=True,
        hovermode="y unified",
        yaxis_title=" ",
        **_LAYOUT_BASE,
    )
    return fig


if __name__ == '__main__':
    app.run_server(host='127.0.0.1', port=8500, use_reloader=False)
