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
#from dash.exceptions import PreventUpdate
import pandas as pd
import sqlite3
#runs backend when frontend is run
from pseudobackend import tagnames

#tagnames from backend
tagnames = tagnames

#connecting to local test db
conn = sqlite3.connect("testdb.db", check_same_thread=False)

#these are both the information queries
#when the real backend is hooked the query section will change to atleast have a limit (max 160k tuples tested)
def getdb(conn):
    result = pd.read_sql_query("Select * FROM test", conn)
    return result

def getambient(conn):
    ambientdataframe = pd.read_sql_query("Select * From test2", conn)
    ambientdataframe["KeyTime"]=ambientdataframe.KeyTime.astype('datetime64[ns]')
    return ambientdataframe

df = getdb(conn)

app = dash.Dash(__name__, prevent_initial_callbacks=False)

#overall layout of the website, put global stuff here (ie the interval update)
app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content'),
    dcc.Interval(
        #this is the main interval update for the website
        id='interval-component',
        interval=5*1000, # in milliseconds
        n_intervals=0
    ),
    #dcc store was experimented for a bit (storing the query in local or memeory as a json, but with large queries it did not really work)
    #dcc.Store(id='dfstore'),
    html.Div(id='hidden-div', style={'display':'none'}),
])

#main update callback, every 5 seconds (based on interval comp) will create a new CSV based on getDB query
#every time this happens it updates a hidden element which triggers a cascade update for all callbacks which have the hidden element as input (any callback which needs queried data)
#this was done as opposed to set all on the update interval bc sometimes they intervals would clash on CSV creation and not have full data
#if the query is small enough each callback that needs data can be changed to just query the local db
#but with 160k elements this method allowed for the largest queries while the website still works
@app.callback(Output('hidden-div', 'children'),
        Input('interval-component', 'n_intervals'))
def update_df(nint):
    df = getdb(conn)
    df.to_csv("currdf.csv", index=False)
    return 0

#1st page
statemap = html.Div([
    html.Div(
    children=[html.H2("Bart Station Map and Status")],
    style=dict(display='flex', justifyContent='center')
    ),
    dcc.Graph(id="mapgraph"),
    #dcc.Interval(
    #   this interval would only be used for map, but it is currently using main page update cascade
    #    id='interval-component2',
    #    interval=10*1000, # in milliseconds
    #    n_intervals=0
    #),
])
#callback for updating status map
@app.callback(Output('mapgraph', 'figure'),
            #Input('interval-component2', 'n_intervals'),
            Input('hidden-div', 'children')
           #State('dfstore','data')
           )
def update_output1(nint):
    result = pd.read_csv("currdf.csv")
    result["KeyTime"]=result.KeyTime.astype('datetime64[ns]')

    locs = pd.read_csv("Locs.csv")
    #fiesta code (this block of code filters down query to get current status per station)
    
    mostrecenttime = result.loc[result.groupby(["Location"])["KeyTime"].idxmax()]
    allmrts = result[result["KeyTime"].isin(mostrecenttime["KeyTime"])]

    highonly = allmrts[allmrts.apply(lambda x: 'High Alert' in x.values, axis=1)]

    allmrts = allmrts[~allmrts["Location"].isin(highonly["Location"])]
    medonly = allmrts[allmrts.apply(lambda x: 'Medium Alert' in x.values and "High Alert" not in x.values, axis=1)]

    allmrts = allmrts[~allmrts["Location"].isin(medonly["Location"])]
    clearonly = allmrts[allmrts.apply(lambda x: 'clear' in x.values and "High Alert" not in x.values and "Medium Alert" not in x.values, axis=1)]
    allalrts = pd.concat([medonly.groupby("Location").head(1), highonly.groupby("Location").head(1),clearonly.groupby("Location").head(1)])

    allalrts["color"] =  allalrts.apply(lambda x: "High Alert" if 'High Alert' in x.values else ('Medium Alert' if "Medium Alert" in x.values else "clear"), axis=1)

    locs = locs.rename(columns={"root__stations__station__name": "Location"})
    localrts = pd.merge(allalrts,locs, on="Location")

    fig = px.scatter_mapbox(localrts,
        lat=localrts['root__stations__station__gtfs_latitude'],
        lon=localrts['root__stations__station__gtfs_longitude'],
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

#callback for page redirect on mapclick
@app.callback(Output('url', 'pathname'),
              Input('mapgraph', 'clickData'))
def mapclick(statdclick):
        return f"/locviewer"

#2nd page  
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
            id = 'Loc'),
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
        dcc.Dropdown(
            id = 'times'),
        ],
        style=dict(width='50%')
        ),
        Download(id="download"),
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
        #only used in battery life interval
        #all other interval updates on this page are based off of the main page layout (interval component)
        id='interval-component3',
        interval=10*1000, # in milliseconds
        n_intervals=0
    ),
])
#callback for updating location dropdown
@app.callback(Output('Loc', 'options'),
              #Input('interval-component3', 'n_intervals')
              Input('hidden-div', 'children')
              )
def update_locdrop(nint):
    df = pd.read_csv("currdf.csv")
    df["KeyTime"]=df.KeyTime.astype('datetime64[ns]')
    return [{'label': i, 'value': i} for i in df.Location.unique()]

#callback for updating error table
@app.callback(
    [Output('table', 'data'),
    Output('table','columns')],
    [Input('Loc', 'value'),
    Input('Tags', 'value'),
    #Input('interval-component3', 'n_intervals')
    Input('hidden-div', 'children')
    ])
def updateTable(Locname, Tag, nint):
    if Locname is not None and Tag is not None:
        df = pd.read_csv("currdf.csv")
        df["KeyTime"]=df.KeyTime.astype('datetime64[ns]')
        #might wanna change to contains (not tested for RT)
        #prob limit more columns for visability
        df = df[(df["Location"] == Locname) & (df[Tag] != "clear")]
        col = [{"name": i, "id": i} for i in list(df.columns)]
        return df.to_dict('records'), col
    return [],[]

#callback for updating location cells facet graph
@app.callback(
    Output("graph", "figure"), 
    [Input("Loc", "value"),
    Input("yaxis", "value"),
    Input('Tags', 'value'),
    Input('rangeslider', 'value'),
    #Input('interval-component3', 'n_intervals')
    Input('hidden-div', 'children')
    ])
def update_graph(Locname, yaxisname, Tag, srange, nint):
    fig=go.Figure()
    if Locname is not None and yaxisname is not None is not Tag is not None and srange is not None:
        df = pd.read_csv("currdf.csv")
        df["KeyTime"]=df.KeyTime.astype('datetime64[ns]')
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
    return fig

#callback for downloading CSV
@app.callback(Output("download", "data"), 
    [Input("times", "value"),
    Input("Loc", "value")])
def generate_csv(drtime, Locname):
    if Locname is not None and drtime is not None:
        df = pd.read_csv("currdf.csv")
        df["KeyTime"]=df.KeyTime.astype('datetime64[ns]')
        df = df[(df["Location"] == Locname) & (df["KeyTime"] == drtime)]
        #can do stuff  to dataframe here (trim down columns or w/e)
        return send_data_frame(df.to_csv, filename="battdata.csv", index=False)

#callback for updating time dropdown
@app.callback(Output('times', 'options'),
              [Input('Loc', 'value'),
              #Input('interval-component3', 'n_intervals')
              Input('hidden-div', 'children')
              ])
def update_timedrop(Locname, nint):
    if Locname is not None:
        df = pd.read_csv("currdf.csv")
        df["KeyTime"]=df.KeyTime.astype('datetime64[ns]')
        df = df[df["Location"] == Locname]
        return [{'label': i, 'value': i} for i in df.KeyTime.dt.strftime('%B %d, %Y, %r').unique()]
    return []

#callback for cell slider
@app.callback(Output('rangeslider', 'max'),
              Input('Loc', 'value'))
def update_slider(Locname):
    if Locname is not None and Locname == "Daly City Station":
        #not really necessary to do this but can be changed back
        #changed to help RT (less queries to csv also not connected to hidden elemet so breaks could happen) 
        #if want to use the query update for this add hidden element as input
        #df = pd.read_csv("currdf.csv")
        #df["KeyTime"]=df.KeyTime.astype('datetime64[ns]')
        #df = df[df["Location"] == Locname]
        #max = round(int(df["CellNo"].max()))
        #return max
            return 180
    return 60

#callback for cell slider string output
@app.callback(Output('range-slider-label', 'children'),
    [Input('rangeslider', 'value')])
def update_output(value):
    return 'Cells {} are selected for viewing'.format(value)

#callback for ambient life battery table
@app.callback(
    [Output('tablel', 'data'),
    Output('tablel','columns')],
    [Input("Loc", "value"),
    Input('interval-component3', 'n_intervals')])
def ambientcall(Locname, nint):
    if Locname is not None:
        #ambientdataframe = pd.read_sql_query(query2, conn)
        ambientdataframe = getambient(conn)
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