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

# Get Cursor not used
cur = conn.cursor()

#moved to outside to mimic actual backend (cant set up until we have packets)
query = """select history.cells.KeyTime, Location, CellNo, VoltValue, ResistValue, TempValue, TotalVolt, TotalCurrent, AmbientTemp from history.cells, info.bankinfo, history.bankdata 
        where history.bankdata.BankId = info.bankinfo.BankId and history.bankdata.KeyTime = history.cells.KeyTime and info.bankinfo.BankId = history.cells.BankId order by Location"""

#used for battery life (parameterizing this is actually slower)
query2 = """select history.bankdata.KeyTime, Location, AmbientTemp from info.bankinfo, history.bankdata 
        where history.bankdata.BankId = info.bankinfo.BankId"""

#used for map with live data (will also include the colors)
query3 = """select history.cells.KeyTime, Location from history.cells, info.bankinfo 
        where info.bankinfo.BankId = history.cells.BankId and KeyTime in (select max(KeyTime) from history.cells, info.bankinfo 
                                                                            where info.bankinfo.BankId = history.cells.BankId group by Location)"""
                                                                            

df1 = pd.read_sql_query(query, conn)

#testmean.csv is our battery commisioning feature
df2 = pd.read_csv("CurrentBaseline.csv")
#make little script for new baseline
#df2 = df.groupby(["Location", "CellNo"], as_index=False).mean() <- made by 6 month data using this call (then do df to csv)
df2.columns = ["Location", "CellNo","VoltMean", "ResistMean", "TempMean"]

df3 = df1.groupby(["KeyTime","Location"], as_index=False).mean()
#calculates temp per location and keytime
df3=df3.rename(columns = {'TempValue':'TempValuetest'})

#result = pd.merge(df1, df2 on=["Location","CellNo"])
result = df1.merge(df2[["Location", "CellNo","ResistMean"]],on=["Location","CellNo"]).merge(df3[["KeyTime","Location","TempValuetest"]],on=["KeyTime","Location"])

#all normal tags are blue, I separated all different tags into columns to avoid stacking errors (this could be useful?)
#ease of changing tagnames
tagnames = ["+-30% Resist", "AmbT > 30", "Cell Temp > AmbT+3", "Tag4", "Cell Temp > 25"]

result[tagnames[0]] = "clear"
result[tagnames[1]] = "clear"
result[tagnames[2]] = "clear"
result[tagnames[3]] = "clear"
result[tagnames[4]] = "clear"

#though this looks repeatative it is ALOT faster than the for loop
#tag number 1 30% deviation from set means (adjacent cells to this one need to be logged)
result.loc[(result["ResistValue"] <= .70*result["ResistMean"]) | (result["ResistValue"] >= 1.3*result["ResistMean"]), tagnames[0]] = "Medium Alert" #"+-30% Resist"
#tag number 2 ambient temp > 30 (current none in our dataset)
result.loc[(result["AmbientTemp"] > 30), tagnames[1]] = "High Alert" #"AmbT > 30"
#tag number 3 cell > total temp + 3
result.loc[(result["TempValue"] > 3+result["AmbientTemp"]), tagnames[2]] = "High Alert" #"Cell Temp > AmbT+3"
#tag 4 (idk what ripple current is yet)
#result.at[i, "VoltValue"]/result.at[i, "ResistValue"] > .0005*result.at[i, "TotalCurrent"]:
#tag 5
#result.loc[(result["TempValue"] > 3+ result["TempValuetest"]), "Tag5"] = "orange"
result.loc[(result["TempValue"] > 25), tagnames[4]] = "Medium Alert" #"Cell Temp > 25"

#setting up locs for map
locs = pd.read_csv("Locs.csv")

#highlight boxes (maybe?) 

#structure for iterating through dataframe with for loop (alot slower runtime)
#for i in result.index:
#    if result.at[i,"ResistValue"] <= .70*result.at[i,"ResistMean"] or result.at[i, "ResistValue"] >= 1.3*result.at[i, "ResistMean"]:
#        result.at[i, 'Tag'] = "red"
#    if result.at[i, "TempValue"] > result.at[i, "AmbientTemp"]+3:
#        result.at[i, 'Tag'] = "yellow"
#    #if result.at[i, "VoltValue"]/result.at[i, "ResistValue"] > .0005*result.at[i, "TotalCurrent"]:
#    #    result.at[i, 'Tag'] = "orange"

#will prob be deleted bc can just use pd read for querys we'll see tho
def getdb(conn,cur):
    #this will simply return the a query of a db (made to better mimic an actual system when we have the packets and a separate backend) 
    return result

df = getdb(conn,cur)

app = dash.Dash(__name__, prevent_initial_callbacks=False)

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
    #fiesta code

    #this part will be replaced by query3 when have live data
    test = result.loc[result.groupby(["Location"])["KeyTime"].idxmax()]
    test2 = result[result["KeyTime"].isin(test["KeyTime"])]

    test3 = test2[test2.apply(lambda x: 'High Alert' in x.values, axis=1)]

    test2 = test2[~test2["Location"].isin(test3["Location"])]
    test4 = test2[test2.apply(lambda x: 'Medium Alert' in x.values and "High Alert" not in x.values, axis=1)]

    test2 = test2[~test2["Location"].isin(test4["Location"])]
    test5 = test2[test2.apply(lambda x: 'clear' in x.values and "High Alert" not in x.values and "Medium Alert" not in x.values, axis=1)]
    test6 = pd.concat([test4.groupby("Location").head(1), test3.groupby("Location").head(1),test5.groupby("Location").head(1)])

    test6["color"] =  test6.apply(lambda x: "High Alert" if 'High Alert' in x.values else ('Medium Alert' if "Medium Alert" in x.values else "clear"), axis=1)

    locs = locs.rename(columns={"root__stations__station__name": "Location"})
    test7 = pd.merge(test6,locs, on="Location")

    fig = px.scatter_mapbox(test7,
        lat=test7['root__stations__station__gtfs_latitude'],
        lon=test7['root__stations__station__gtfs_longitude'],
        hover_name="Location",
        hover_data=tagnames,
        mapbox_style="open-street-map",
        color="color",
        height = 1000,
        color_discrete_map={
            "clear": "blue",
            "High Alert": "red",
            "Medium Alert":"yellow",}
        )
    fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, uirevision=True)    
    fig.update_traces(marker=dict(size=20)),
    return fig
@app.callback(Output('url', 'pathname'),
              Input('mapgraph', 'clickData'))
def mapclick(statdclick):
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
            options=[{'label': i, 'value': i} for i in tagnames]),   
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
        html.Label(['Select Data Time to Download:'], style={'font-weight': 'bold', "text-align": "center"}),
        #prob delete this and go back to the dropdown menu
        #dcc.DatePickerRange(
        #id = 'Time',
        #display_format='M-D-Y',
        #start_date_placeholder_text="Start Date",
        #end_date_placeholder_text="End Date",
        #minimum_nights=0,
        #has to update with n intervals
        #min_date_allowed=df.KeyTime.min(),
        #max_date_allowed=df.KeyTime.max(),
        #clearable=True,
        #),
        #this dropdown needs to update from Locations DR
        dcc.Dropdown(
            id = 'times', 
            #options=[{'label': i, 'value': i} for i in df.KeyTime.dt.strftime('%B %d, %Y, %r').unique()]
            ),
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
    dcc.Interval(
        id='interval-component2',
        interval=5*1000, # in milliseconds
        n_intervals=0
    ),
])
@app.callback(Output('Loc', 'options'),
              [Input('interval-component2', 'n_intervals')])
def update_timedrop(nint):
    df = getdb(conn,cur)
    return [{'label': i, 'value': i} for i in df.Location.unique()]

@app.callback(
    [Output('table', 'data'),
    Output('table','columns')],
    [Input('Loc', 'value'),
    Input('Tags', 'value'),
    Input('interval-component2', 'n_intervals')])
def updateTable(Locname, Tag, nint):
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
    Input('rangeslider', 'value'),
    Input('interval-component2', 'n_intervals')])
def update_graph(Locname, yaxisname, Tag, srange, nint):
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
        fig.update_layout(uirevision=True)
        #this adds the line but also an extreme amount of lag so prob avoid
        #if yaxisname == "TempValue":
        #    fig.add_shape(type="line", x0=df.KeyTime.min(), y0=25, x1=df.KeyTime.max(),y1=25, row="all", col="all",exclude_empty_subplots=True)
    return fig

@app.callback(Output("download", "data"), 
    [
    #Input("btn", "n_clicks_timestamp"), scrapping download button for now
    Input("times", "value"),
    #Input('Time', 'start_date'),
    #Input('Time', 'end_date'),
    Input("Loc", "value"),
    ])
def generate_csv(drtime, Locname):
    if Locname is not None and drtime is not None:
        df = getdb(conn,cur)
        print(drtime)
        df = df[(df["Location"] == Locname) & (df["KeyTime"] == drtime)]
        #can do stuff  to dataframe here
        return send_data_frame(df.to_csv, filename="battdata.csv", index=False)

@app.callback(Output('times', 'options'),
              [Input('Loc', 'value'),
              Input('interval-component2', 'n_intervals')])
def update_timedrop(Locname, nint):
    if Locname is not None:
        df = getdb(conn,cur)
        df = df[df["Location"] == Locname] 
        return [{'label': i, 'value': i} for i in df.KeyTime.dt.strftime('%B %d, %Y, %r').unique()]
    return [1]

@app.callback(Output('rangeslider', 'max'),
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
    [Input("Loc", "value"),
    Input('interval-component2', 'n_intervals')])
def ambientcall(Locname, nint):
    if Locname is not None:
        ambientdataframe = pd.read_sql_query(query2, conn)
        ambientdataframe.set_index('KeyTime', inplace=True)
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