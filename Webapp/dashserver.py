import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash_extensions import Download
from dash_extensions.snippets import send_data_frame
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go
import dash_table

import mariadb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime as dt
import sys

try:
    conn = mariadb.connect(
        user="root",
        password="admin1234",
        host="127.0.0.1",
        port=3306,
    )
except mariadb.Error as e:
    print(f"Error connecting to MariaDB Platform: {e}")
    sys.exit(1)

# Get Cursor
cur = conn.cursor()

#moved to outside to mimic actual backend (cant set up until we have packets)
query = """select history.cells.KeyTime, Location, CellNo, VoltValue, ResistValue, TempValue, TotalVolt, TotalCurrent, AmbientTemp from history.cells, info.bankinfo, history.bankdata 
        where history.bankdata.BankId = info.bankinfo.BankId and history.bankdata.KeyTime = history.cells.KeyTime and info.bankinfo.BankId = history.cells.BankId order by Location"""

query2 = """select history.bankdata.KeyTime, Location, AmbientTemp from info.bankinfo, history.bankdata 
        where history.bankdata.BankId = info.bankinfo.BankId"""
ambientdataframe = pd.read_sql_query(query2, conn)
ambientdataframe.set_index('KeyTime', inplace=True)

df1 = pd.read_sql_query(query, conn)

#testmean.csv is our battery commisioning feature
df2 = pd.read_csv("CurrentBaseline.csv")
#df2 = df.groupby(["Location", "CellNo"], as_index=False).mean() <- made by 6 month data using this call (then do df to csv)
df2.columns = ["Location", "CellNo","VoltMean", "ResistMean", "TempMean"]

df3 = df1.groupby(["KeyTime","Location"], as_index=False).mean()
#calculates temp per location and keytime
df3=df3.rename(columns = {'TempValue':'TempValuetest'})

#result = pd.merge(df1, df2 on=["Location","CellNo"])
result = df1.merge(df2[["Location", "CellNo","ResistMean"]],on=["Location","CellNo"]).merge(df3[["KeyTime","Location","TempValuetest"]],on=["KeyTime","Location"])

#all normal tags are blue, I separated all different tags into columns to avoid stacking errors (this could be useful?)
result["Tag1"] = "clear"
result["Tag2"] = "clear"
result["Tag3"] = "clear"
result["Tag4"] = "clear"
result["Tag5"] = "clear"

#though this looks repeatative it is ALOT faster than the for loop
#tag number 1 30% deviation from set means (adjacent cells to this one need to be logged)
result.loc[(result["ResistValue"] <= .70*result["ResistMean"]) | (result["ResistValue"] >= 1.3*result["ResistMean"]), "Tag1"] = "red" #"+-30% Resist"
#tag number 2 ambient temp > 30 (current none in our dataset)
result.loc[(result["AmbientTemp"] > 30), "Tag2"] = "red" #"AmbT > 30"
#tag number 3 cell > total temp + 3
result.loc[(result["TempValue"] > 3+result["AmbientTemp"]), "Tag3"] = "yellow" #"Cell Temp > AmbT+3"
#tag 4 (idk what ripple current is yet)
#result.at[i, "VoltValue"]/result.at[i, "ResistValue"] > .0005*result.at[i, "TotalCurrent"]:
#tag 5
#result.loc[(result["TempValue"] > 3+ result["TempValuetest"]), "Tag5"] = "orange"
result.loc[(result["TempValue"] > 25), "Tag5"] = "yellow" #"Cell Temp > 25"

#setting up locs for map
locs = pd.read_csv("Locs.csv")

#highlight boxes
#outlier for graphs above 25
#alerts status bubble
#for map graph color will be based off of alerts and can have a DSM for each alert ez
#discrete color map (can use to determine error bubble)
#prob make a two page app
#be based off of most recent errors
#be based off of latest time and severity of errors
#first page is all locs second page is a redirect

#structure for iterating through dataframe with for loop (alot slower runtime)
#for i in result.index:
#    if result.at[i,"ResistValue"] <= .70*result.at[i,"ResistMean"] or result.at[i, "ResistValue"] >= 1.3*result.at[i, "ResistMean"]:
#        result.at[i, 'Tag'] = "red"
#    if result.at[i, "TempValue"] > result.at[i, "AmbientTemp"]+3:
#        result.at[i, 'Tag'] = "yellow"
#    #if result.at[i, "VoltValue"]/result.at[i, "ResistValue"] > .0005*result.at[i, "TotalCurrent"]:
#    #    result.at[i, 'Tag'] = "orange"

def getdb(conn,cur):
    #this will simply return the a query of a db (made to better mimic an actual system when we have the packets and a separate backend) 
    return result

df = getdb(conn,cur)

fig = px.scatter_mapbox(locs,
        lat=locs['root__stations__station__gtfs_latitude'],
        lon=locs['root__stations__station__gtfs_longitude'],
        hover_name="root__stations__station__name",
        mapbox_style="open-street-map",
        height = 1000
        )
fig.update_traces(marker=dict(size=20))
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, uirevision=True)

app = dash.Dash(__name__, prevent_initial_callbacks=True)

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

statemap = html.Div([
    html.Div(
    children=[html.H2("Bart Station Map and Status")],
    style=dict(display='flex', justifyContent='center')
    ),
    dcc.Graph(id="mapgraph",
    figure = fig,
    ),
    dcc.Interval(
        id='interval-component',
        interval=5*1000, # in milliseconds
        n_intervals=0
    )
])
@app.callback(Output('mapgraph', 'figure'),
              [Input('interval-component', 'n_intervals')])
def update_output1(n_interval):
    result = getdb(conn,cur)
    locs = pd.read_csv("Locs.csv")

    test = result.loc[result.groupby(["Location"])["KeyTime"].idxmax()]
    test2 = result[result["KeyTime"].isin(test["KeyTime"])]
    test3 = test2[test2.apply(lambda x: 'red' in x.values, axis=1)]

    test2 = test2[~test2["Location"].isin(test3["Location"])]
    test4 = test2[test2.apply(lambda x: 'yellow' in x.values and "red" not in x.values, axis=1)]

    test2 = test2[~test2["Location"].isin(test4["Location"])]
    test5 = test2[test2.apply(lambda x: 'clear' in x.values and "red" not in x.values and "yellow" not in x.values, axis=1)]
    test6 = pd.concat([test4.groupby("Location").head(1), test3.groupby("Location").head(1),test5.groupby("Location").head(1)])

    test6["color"] = "blue"
    test6.loc[((test6["Tag3"] == "yellow") | (test6["Tag4"] == "yellow") | (test6["Tag5"] == "yellow")), "color"] = "yellow"
    test6.loc[((test6["Tag1"] == "red") | (test6["Tag1"] == "red")), "color"] = "red"
    locs = locs.rename(columns={"root__stations__station__name": "Location"})
    test7 = pd.merge(test6[["Location", "color"]],locs, on="Location")

    fig = px.scatter_mapbox(test7,
        lat=test7['root__stations__station__gtfs_latitude'],
        lon=test7['root__stations__station__gtfs_longitude'],
        hover_name="Location",
        mapbox_style="open-street-map",
        color="color",
        height = 1000,
        color_discrete_map={
            "blue": "blue",
            "red": "red",
            "yellow":"yellow",}
        )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, uirevision=True)    
    fig.update_traces(marker=dict(size=20)),
    return fig
@app.callback(Output('url', 'pathname'),
              Input('mapgraph', 'clickData'))
def display_page(statdclick):
        return f"/locviewer"
        
locviewer = html.Div([
    html.Div(
    children=[html.H2("Bart Battery Location Viewer")],
    style=dict(display='flex', justifyContent='center')
    ),
    html.Br(),
    dcc.Link('Go back to Map', href='/map'),
    html.Div(className = "row", children=[
        html.Div(className="four columns", children=[
            html.Label(['Locations:'], style={'font-weight': 'bold', "text-align": "center"}),
            dcc.Dropdown(
            id = 'Loc', 
            options=[{'label': i, 'value': i} for i in df.Location.unique()]),
        ],style=dict(width='33.33%')),
        html.Div(className="four columns", children=[
            html.Label(['Y-Axis:'], style={'font-weight': 'bold', "text-align": "center"}),
            dcc.Dropdown(
            id = 'yaxis', 
            options=[{'label': i, 'value': i} for i in list(df)]),
        ],style=dict(width='33.33%')),
        html.Div(className="four columns", children=[
            html.Label(['Error Type:'], style={'font-weight': 'bold', "text-align": "center"}),
            dcc.Dropdown(
            id = 'Tags', 
            options=[{'label': i, 'value': i} for i in ["Tag1", "Tag2", "Tag3", "Tag4", "Tag5"]]),   
        ],style=dict(width='33.33%')),
    ],style=dict(display='flex')),
    html.Div(children=[
    html.Label(['Cell Range:'], style={'font-weight': 'bold', "text-align": "center"}),
    html.Div(id='range-slider-label'),
    dcc.RangeSlider(
        id='rangeslider',
        min=0,
        step=1,
    ),
    ]),
    html.Div(children=[
        html.Div(
        children=[
        html.Label(['Select Data Range to Download:'], style={'font-weight': 'bold', "text-align": "center"}),
        dcc.DatePickerRange(
        id = 'Time',
        display_format='M-D-Y',
        start_date_placeholder_text="Start Date",
        end_date_placeholder_text="End Date",
        minimum_nights=0,
        #has to update with n intervals
        min_date_allowed=df.KeyTime.min(),
        max_date_allowed=df.KeyTime.max(),
        clearable=True,
        ),
        #can use this or the date range (ask mentors next meeting)
        dcc.Dropdown(
            id = 'times', 
            options=[{'label': i, 'value': i} for i in df.KeyTime.dt.date.unique()]),
        ],
        style=dict(width='50%')
        ),
        #html.Div(
        #children=[html.Button("Download csv", id="btn"), 
        Download(id="download"),
        Download(id="download2"),
        #],
        #style=dict(width='50%', display='flex')
        #),
    ],),
    dcc.Graph(id="graph"),
    html.H2("Errors/Outliers"),
    dash_table.DataTable(
        id = 'table',
        style_data={ 'border': '1px solid grey' },
        virtualization=True,
    ),
    html.H2("Battery Life"),
    dash_table.DataTable(
        id = 'tablel',
        style_data={ 'border': '1px solid grey' },
        virtualization=True,
    ),
])

@app.callback(
    [Output('table', 'data'),
    Output('table','columns')],
    [Input('Loc', 'value'),
    Input('Tags', 'value')])
def updateTable(Locname, Tag):
    if Locname is not None and Tag is not None:
        df = getdb(conn,cur) 
        #might wanna change to contains
        #prob limit more columns for visability
        df = df[(df["Location"] == Locname) & (df[Tag] != "clear")]
        col = [{"name": i, "id": i} for i in list(df.columns)]
        return df.to_dict('records'), col
    return [],[]

@app.callback(
    Output("graph", "figure"), 
    [Input("Loc", "value"),
    Input("yaxis", "value"),
    Input('Tags', 'value'),
    Input('rangeslider', 'value')])
def update_graph(Locname, yaxisname, Tag, srange):
    #im like 60% sure this is causing some errors (webpage randomly refreshes) I may have fixed it tho
    fig = go.Figure()
    if Locname is not None and yaxisname is not None is not Tag is not None and srange is not None:
        df = getdb(conn,cur)
        df = df[(df["Location"] == Locname) & (df["CellNo"] >= srange[0]) & (df["CellNo"] <= srange[1])]
        wrap = 6
        if Locname == "Daly City Station":
            wrap = 12
        if srange[1]-srange[0] < 10:
            gheight = 300
        else:
            gheight = 30*(srange[1]-srange[0])
        fig = px.scatter(df, x="KeyTime", y=yaxisname, color=Tag, facet_col="CellNo",facet_col_wrap=wrap, height=gheight,
                    color_discrete_map={
                        "clear": "blue"})
        fig.update_yaxes(matches=None, showticklabels=True)
    return fig

@app.callback(Output("download", "data"), 
    [
    #Input("btn", "n_clicks_timestamp"), scrapping download button for now
    Input('Time', 'start_date'),
    Input('Time', 'end_date'),
    Input("Loc", "value"),
    ])
def generate_csv(start, end, Locname):
    if start is not None and end is not None and Locname is not None:
        df = getdb(conn,cur)
        df = df[(df["Location"] == Locname) & (df["KeyTime"] >= start) & (df["KeyTime"] <= end)]
        #can do stuff  to dataframe here
        return send_data_frame(df.to_csv, filename="battdata.csv", index=False)

@app.callback([Output('rangeslider', 'max')],
              [Input('Loc', 'value')])
def update_slider(Locname):
    if Locname is not None:
        df = getdb(conn,cur)
        df = df[df["Location"] == Locname]
        max = round(int(df["CellNo"].max())),
        return max
    return [0]

@app.callback(Output('range-slider-label', 'children'),
    [Input('rangeslider', 'value')])
def update_output(value):
    return 'Cells {} are selected for viewing'.format(value)

@app.callback(
    [Output('tablel', 'data'),
    Output('tablel','columns')],
    [Input("Loc", "value"),])
def generate_csv(Locname):
    if Locname is not None:
        df2 = ambientdataframe[ambientdataframe["Location"] == Locname]

        temp = 0
        previ = 0
        lst = []
        for i in df2.index:
            if df2.at[i, "AmbientTemp"] >= 25 and temp == 0:
                temp = i
            if df2.at[i, "AmbientTemp"] < 25 and temp != 0 and temp < previ:
                lst.append([temp, previ, str(previ - temp)])
                temp = 0
            previ = i
        df2 = pd.DataFrame(lst)
        df2.columns = ["TimeStart","TimeEnd", "Length"]
        col = [{"name": i, "id": i} for i in list(df2.columns)]
        return df2.to_dict('records'), col
    return [],[]

# return page
@app.callback(dash.dependencies.Output('page-content', 'children'),
              [dash.dependencies.Input('url', 'pathname')])
def display_page(pathname):
    if pathname == '/locviewer':
        return locviewer
    else:
        return statemap
app.run_server(debug=False)