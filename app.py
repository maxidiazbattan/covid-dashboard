# Importing the libraries.

# tools
import os
import gc
from urllib.request import urlretrieve

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

    # OWID covid Dataset URL:
    url = 'https://covid.ourworldindata.org/data/owid-covid-data.csv'

    # Retrieve .CSV file from OWID
    urlretrieve(url, 'owid-covid-data.csv')

    # Read the file with polars
    data = pl.read_csv('owid-covid-data.csv')

    use_cols = ['iso_code', 'continent', 'location', 'date', 'total_deaths', 'total_cases', 'new_cases_per_million', 'new_deaths_per_million',
                'total_tests_per_thousand','new_tests_per_thousand', 'hospital_beds_per_thousand', 'total_vaccinations_per_hundred', 
                'people_vaccinated_per_hundred', 'people_fully_vaccinated_per_hundred', 'total_boosters_per_hundred']

    data = data.select(use_cols)

    # Delete the file
    # os.remove('owid-covid-data.csv')
    gc.collect()

    # Conversion to datetime
    data = data.with_columns(pl.col('date').str.strptime(pl.Datetime, strict=False))

    # Creating 3 columns with the year, month, and day respectively

    data = data.with_columns(
        pl.col("date").dt.year().alias('year'),
        pl.col("date").dt.month().alias('month'),
        pl.col("date").dt.day().alias('day'),
        )

    # Filtering
    years = [2020, 2021, 2022]
    data = data.filter(pl.col('year').is_in(years))

    # Unifying units of measure
    data = data.with_columns(
        pl.col('new_cases_per_million').cast(pl.Float32, strict=False),
        pl.col('new_deaths_per_million').cast(pl.Float32, strict=False),
        (pl.col('total_tests_per_thousand').cast(pl.Float32, strict=False) * 1000).alias('total_tests_per_million'),
        (pl.col('new_tests_per_thousand').cast(pl.Float32, strict=False) * 1000).alias('new_tests_per_million'),
        (pl.col('hospital_beds_per_thousand').cast(pl.Float32, strict=False) * 1000).alias('hospital_beds_per_million'),
        (pl.col('total_vaccinations_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('total_vaccinations_per_million'),
        (pl.col('people_vaccinated_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('people_vaccinated_per_million'),
        (pl.col('people_fully_vaccinated_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('people_fully_vaccinated_per_million'),
        (pl.col('total_boosters_per_hundred').cast(pl.Float32, strict=False) * 10000).alias('total_boosters_per_million'),
                    )

    use_cols = ['iso_code', 'continent', 'location', 'date', 'total_deaths', 'total_cases', 'new_cases_per_million', 'new_deaths_per_million',
                'total_tests_per_million','new_tests_per_million', 'hospital_beds_per_million', 'total_vaccinations_per_million', 
                'people_vaccinated_per_million', 'people_fully_vaccinated_per_million', 'total_boosters_per_million']

    return data.select(use_cols).to_pandas()
    
data = load_data()

select_continent = {x : x for x in data["continent"].dropna().unique()}

app = dash.Dash(__name__,external_stylesheets = [dbc.themes.CYBORG],
                         meta_tags=[{'name': 'viewport',
                                     'content': 'width=device-width, initial-scale=1.0'
                           }] 
                ) # [dbc.themes.CYBORG]) 
server = app.server

app.layout = dbc.Container([

    # dbc.Row(dbc.Col(html.P(children="💉", className="header-emoji text-center"), width=12)),
    # dbc.Row(dbc.Col(html.H1("COVID-19 Dashboard 💉", className='header-title text-center mb-2'), width=12)),

    dbc.Row([
        dbc.Col(html.H3("COVID-19 🦠 Tracker", className='header-title text-center mt-4 mb-2'), width=4),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Dropdown(id="continent-dropdown",
                                 options=[{"label": j, "value": i} for i, j in select_continent.items()],
                                 value="Africa",
                                 clearable=False,
                                 style={'justify-content': 'center', 'align-items': 'center', 'widht': '100px'}
                                 # style= {'Width': 'auto', 'align-items': 'center', 'verticalAlign' : "middle", 'horizontalAlign' : "middle"},
                                    ),

                     ]),], className="card text-center mt-2 mb-2"),
                 ], width={'size': 4}),
            # ], justify='center'),
        
    # dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dcc.DatePickerRange(
                                             id='my-date-picker-range',
                                             min_date_allowed=data['date'].min(),
                                             max_date_allowed=data['date'].max(),
                                             initial_visible_month=data['date'].min(),
                                             start_date=data['date'].min(),
                                             end_date=data['date'].max(),
                                             style= {'Width': 'auto', #'100%', 'Height': '30px', 'font-size': '10px',
                                                     'align-items': 'center', 'verticalAlign' : "middle",
                                                     'horizontalAlign' : "middle" }
                                            )
                                            ,])
                            ],className="card text-center mt-2 mb-2"),
                        ],width={'size': 4}, ),
            ],),

    dbc.Row([dbc.Col([dbc.Card([dbc.CardBody([html.Span("Confirmed cases per million", className="card-text text-center"),
                                             html.H3(style={"color": "#389fd6"}, id="casos-confirmados-text"),
                                             html.H5(id="nuevos-casos-text", children="0"),])
                                 ], className="card text-center" )], width=4),

            dbc.Col([dbc.Card([dbc.CardBody([html.Span("Confirmed deaths per million", className="card-text text-center"),
                                             html.H3(style={"color": "#data2935"}, id="muertes-confirmadas-text"),
                                             html.H5(id="muertes-text", children="0"),])
                                ],  className="card text-center" )], width=4),

            dbc.Col([dbc.Card([dbc.CardBody([html.Span("Mortality rate %", className="card-text text-center"),
                                               html.H3(style={"color": "#adatac92"}, id="mortality-rate-text"),
                                               html.H5(id="mortalidad-text", children="0"), ])
                                 ], className="card text-center" )],width=4),
            ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='pie-plot', figure={}),
                 ]),
             ], ),
         ], width=4, className="mt-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='hist1-plot', figure={}),
                ]),
            ], ),
        ], width=4, className="mt-1"),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='hist2-plot', figure={})
                ]),
            ], ),
        ], width=4, className="mt-1"),
    ],),

    dbc.Row([
            dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    dcc.Graph(id='line-plot', figure={})
                ]),
            ], ),
        ], width=12, className="mt-1"),
    ],),


], fluid=True)


# Updating the 3 number cards ******************************************
@app.callback(

    Output('nuevos-casos-text','children'),
    Output('muertes-text','children'),
    Output('mortalidad-text','children'),
    Input('continent-dropdown','value'),
    Input('my-date-picker-range','start_date'),
    Input('my-date-picker-range','end_date'),
)

def display_status(continent, start_date, end_date):

    dfq = data.query(f'continent == "{continent}"')

    start_date = dfq['date'].min()
    end_date = dfq['date'].max()

    dfq = dfq[(dfq['date']>=start_date) & (dfq['date']<=end_date)]

    casos_acumulados = dfq[dfq['date'] == dfq['date'].max()]['total_cases'].sum().astype('int32') / 1_000_000
    muertes_acumulado = dfq[dfq['date'] == dfq['date'].max()]['total_deaths'].sum().astype('int32') / 1_000_000
    mortality_rate = (dfq['total_deaths'] / dfq['total_cases'] * 100).sum() / len(dfq['total_deaths'].dropna())

    return (
             casos_acumulados.round(2),
             muertes_acumulado.round(2),
             mortality_rate.round(2)
            )

# Pie Chart ***********************************************************
@app.callback(
    Output('pie-plot','figure'),
    Input('continent-dropdown','value'),
    Input('my-date-picker-range','start_date'),
    Input('my-date-picker-range','end_date'),
)
def update_pie(continent, start_date, end_date):

    df1 = data.copy()

    df1 = df1.query(f'continent == "{continent}"')
    df1 = df1[(df1['date']>=start_date) & (df1['date']<=end_date)]

    df1 = df1.groupby('location').mean().sort_values(by='new_cases_per_million', ascending=False)[:10]
    fig_pie = px.pie(df1, names=df1.index, values=df1['new_cases_per_million'],hole=0.7,color=df1.index, title='New cases per million')
    fig_pie.update_traces(hovertemplate=None, textposition='inside', textinfo='percent+label', rotation=45)
    fig_pie.update_layout(showlegend=False,
                          plot_bgcolor='#000000', paper_bgcolor='#000000',
                          title=dict(y=0.9, x=0.5, yanchor='top', xanchor='center'),
                          title_font=dict(size=25, color='#8a8d93', family="Lato, sans-serif"),
                          font=dict(color='#8a8d93'),
                          hoverlabel=dict(bgcolor="#c6ccd8", font_size=13, font_family="Lato, sans-serif"))

    return fig_pie


# Hist Chart ***********************************************************
@app.callback(
    Output('hist1-plot','figure'),
    Input('continent-dropdown','value'),
    Input('my-date-picker-range','start_date'),
    Input('my-date-picker-range','end_date'),
)
def update_hist1(continent, start_date, end_date):

    df2 = data.copy()

    df2 = df2.query(f'continent == "{continent}"')
    df2 = df2[(df2['date']>=start_date) & (df2['date']<=end_date)]

    fig_hist1 = px.histogram(data_frame = df2, y = 'location', x = df2['people_fully_vaccinated_per_million'].rolling(7).mean(), color = 'location',
             color_discrete_sequence=px.colors.qualitative.Plotly,
             labels = {'location': 'Country', 'people_fully_vaccinated_per_million': 'Fully vaccinated per million'},
             title = 'Fully vaccinated per million')

    fig_hist1.update_yaxes(showgrid=False, ticksuffix=' ', showline=False, categoryorder='total ascending')
    fig_hist1.update_xaxes(visible=True)

    fig_hist1.update_layout(margin=dict(t=100, b=10, l=70, r=40),showlegend=False,
                            hovermode="y unified",
                            xaxis_title=" ",
                            yaxis_title=" ",
                            plot_bgcolor='#000000', paper_bgcolor='#000000',
                            title=dict(y=0.9, x=0.5, yanchor='top', xanchor='center'),
                            title_font=dict(size=25, color='#8a8d93', family="Lato, sans-serif"),
                            font=dict(color='#8a8d93'),
                            hoverlabel=dict(bgcolor="#c6ccd8", font_size=13, font_family="Lato, sans-serif"))

    return fig_hist1

# Hist Chart ***********************************************************
@app.callback(
    Output('hist2-plot','figure'),
    Input('continent-dropdown','value'),
    Input('my-date-picker-range','start_date'),
    Input('my-date-picker-range','end_date'),
)
def update_hist2(continent, start_date, end_date):

    df3 = data.copy()

    df3 = df3.query(f'continent == "{continent}"')
    df3 = df3[(df3['date']>=start_date) & (df3['date']<=end_date)]

    fig_hist2 = px.histogram(data_frame = df3, y = 'location', x = 'new_deaths_per_million', color = 'location',
                             color_discrete_sequence=px.colors.qualitative.Plotly,
                             labels = {'location': 'Country', 'new_deaths_per_million': 'Deaths per million'},
                             title = 'Deaths per million')

    fig_hist2.update_yaxes(showgrid=False, ticksuffix=' ', showline=False, categoryorder='total ascending')
    fig_hist2.update_xaxes(visible=True)

    fig_hist2.update_layout(margin=dict(t=100, b=10, l=70, r=40),showlegend=False,
                            hovermode="y unified",
                            xaxis_title=" ",
                            yaxis_title=" ",
                            plot_bgcolor='#000000', paper_bgcolor='#000000',
                            title=dict(y=0.9, x=0.5, yanchor='top', xanchor='center'),
                            title_font=dict(size=25, color='#8a8d93', family="Lato, sans-serif"),
                            font=dict(color='#8a8d93'),
                            hoverlabel=dict(bgcolor="#c6ccd8", font_size=13, font_family="Lato, sans-serif"))

    return fig_hist2

# Line Chart ***********************************************************
@app.callback(
    Output('line-plot','figure'),
    Input('continent-dropdown','value'),
    Input('my-date-picker-range','start_date'),
    Input('my-date-picker-range','end_date'),
)
def update_line(continent, start_date, end_date):

    df4 = data.copy()

    df4 = df4.query(f'continent == "{continent}"')
    df4 = df4[(df4['date']>=start_date) & (df4['date']<=end_date)]

    fig_line = px.area(data_frame = df4, x = 'date', y = 'new_cases_per_million', color = 'location',
                       color_discrete_sequence=px.colors.qualitative.Plotly,
                       labels = {'location': 'Country', 'new_cases_per_million': 'Cases per million'},
                       title = 'Cases per million')

    fig_line.update_yaxes(showgrid=False, ticksuffix=' ', showline=False, categoryorder='total ascending')
    fig_line.update_xaxes(visible=False)

    fig_line.update_layout(margin=dict(t=100, b=10, l=70, r=40),showlegend=True,
                           hovermode="y unified",
                           yaxis_title=" ",
                           plot_bgcolor='#000000', paper_bgcolor='#000000',
                           title=dict(y=0.9, x=0.5, yanchor='top', xanchor='center'),
                           title_font=dict(size=25, color='#8a8d93', family="Lato, sans-serif"),
                           font=dict(color='#8a8d93'),
                           hoverlabel=dict(bgcolor="#c6ccd8", font_size=13, font_family="Lato, sans-serif"))

    return fig_line


if __name__ =='__main__':
    app.run_server(host='127.0.0.1',port=8500, use_reloader=False)
