import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly
from plotly import graph_objects as go
import plotly.express as px
import pandas as pd
import polars as pl
import numpy as np

# from geopy.geocoders import Photon
from geopy.geocoders import Nominatim
# geolocator = Nominatim(user_agent="my_user_agent")
geolocator = Nominatim(user_agent="Geopy Library")

# Raw_data: save sheet one in the same dir as rawDump_1.csv
raw_dump = pl.read_csv('./rawDump_1.csv',
                         try_parse_dates=True, 
                         encoding='ISO-8859-1')
df = raw_dump.with_columns(
    pl.col('Set up date').cast(pl.Utf8)
    .str.zfill(8).str.strptime(pl.Date, "%m%d%Y"), 
    pl.col('Pick up date').cast(pl.Utf8).str.zfill(8).str.strptime(pl.Date, "%m%d%Y"), 
    pl.col('Start time').str.strptime(pl.Time, "%H:%M"), 
    pl.col('End time').str.strptime(pl.Time, "%H:%M")
).to_pandas()

# Geocode addresses to latitude and longitude
# geolocator = Photon(user_agent="geoapiExercises")
df['location'] = df['Address'].apply(lambda x: geolocator.geocode(x, timeout=None))
df['latitude'] = df['location'].apply(lambda loc: loc.latitude if loc else None)
df['longitude'] = df['location'].apply(lambda loc: loc.longitude if loc else None)

# Columns to be selected from:
shits = [
 'PM2.5 mass (mg)',
 'PM2.5 (µg/m3)',
 'BC (µg/m3)',
 'Ho (µg/g)',
 'Yb (µg/g)',
 'Lu (µg/g)',
 'Ethane, 1,1-dichloro-  (ppb)',
 'n-Hexane  (ppb)',
 'Chloroform  (ppb)',
]

df[shits] = df[shits].fillna(0.)

# Round colors
plotly_colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
rd_colors = {idx : plotly_colors[idx] for idx in range(3)}

# Set up dash
app = dash.Dash(__name__)

app.layout = html.Div([
    html.Label("Select round:"),
    dcc.Checklist(
        id='Round',
        options=df['Round'].unique(),
        value=df['Round'].unique(), # Default value
        # multi=True, 
        inline=True, 
        # disable=True, 
    ),
    html.Label("In Or Out:"), 
    dcc.RadioItems(
        id='InOrOut', 
        options=df['Indoor or outdoor'].unique(), 
        value=df['Indoor or outdoor'].unique()[0], 
    ), 
    html.Label("Select shit:"), 
    dcc.Dropdown(
        id='Shits',
        options=shits,
        value=shits[0], # Default value
        multi=False
    ),
    dcc.Graph(id='my-plot')
])

@app.callback(
    Output('my-plot', 'figure'),
    Input('Round', 'value'), 
    Input('InOrOut', 'value'), 
    Input('Shits', 'value'), 
)
def update_plot(round, inOrOut, shit):
    this_df = df.loc[(df['Round'].isin(round)) & 
                     (df['Indoor or outdoor'] == inOrOut)]
    # Find correct barheight
    median_bar_height = 25
    max_bar_height = 30
    min_bar_height = 20
    this_df[shit] = this_df[shit].clip(lower=0., )
    if this_df[shit].median() == 0.:
        normalizer = this_df[shit].mean()
        if normalizer == 0.:
            this_df[f'plot_{shit}_ht'] = min_bar_height
        else:
            this_df[f'plot_{shit}_ht'] = this_df[shit] / normalizer * median_bar_height
    else:
        normalizer = this_df[shit].median() 
        this_df[f'plot_{shit}_ht'] = this_df[shit] / normalizer * median_bar_height
    
    this_df[f'plot_{shit}_ht'] = this_df[f'plot_{shit}_ht'].clip(lower=min_bar_height, 
                                                                 upper=max_bar_height)
    this_df[f'text_{shit}'] = this_df.apply(lambda row: f"Home ID = {row['Home ID']} \n {shit} = {row[shit]}", axis=1)

    fig = go.Figure()

    for rd in round:
        plot_df = this_df.loc[this_df['Round'] == rd]

        fig.add_traces(go.Scattermap(
            lat=plot_df['latitude'],
            lon=plot_df['longitude'],
            mode='markers',
            marker=go.scattermap.Marker(
                # symbol='square', 
                size=plot_df[f'plot_{shit}_ht'], 
                color=rd_colors[rd], 
                # autocolorscale=True, 
                # colorbar=dict(
                #     title=dict(
                #         text=shit, 
                #     )
                # )
            ),
            customdata=np.stack([plot_df['Home ID'], plot_df[shit]], axis=-1), 
            hovertemplate = "<b> Home ID : %{customdata[0]} <br>" + 
            f"<b>{shit}" + " : %{customdata[1]}", 
            name=f'Round {rd}', 
        ))

    fig.update_layout(
        hovermode='closest',
        autosize=True, 
        width=1200,  # Set the width to 800 pixels
        height=900, # Set the height to 600 pixels
        map=dict(
            bearing=0,
            center=go.layout.map.Center(
                lat=df['latitude'].mean(),
                lon=df['longitude'].mean(), 
            ),
            pitch=0,
            zoom=10, 
        ), 
        showlegend=True, 
        legend=dict(
            orientation='h', 
            xanchor='auto', 
            yanchor='bottom', 
            itemsizing='constant', # Ensures all legend markers have the same size
            traceorder='normal',
            font=dict(
                family='sans-serif',
                size=20,
                color='black'
            ),
        ),
    )
    return fig

if __name__ == '__main__':
    app.run_server(debug=True, 
                   port='8100', 
                   # jupyter_mode='external', 
                  )