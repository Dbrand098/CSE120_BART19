import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
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

df1 = pd.read_sql_query(query, conn)

#testmean.csv is our battery commisioning feature
df2 = pd.read_csv("CurrentBaseline.csv")
#df2 = df.groupby(["Location", "CellNo"], as_index=False).mean() <- made by 6 month data using this call (then do df to csv)
df2.columns = ["Location", "CellNo","VoltMean", "ResistMean", "TempMean"]

result = pd.merge(df1, df2, on=["Location","CellNo"])

#all normal tags are blue, I separated all different tags into columns to avoid stacking errors (this could be useful?)
result["Tag1"] = "blue"
result["Tag2"] = "blue"
result["Tag3"] = "blue"
result["Tag4"] = "blue"

#though this looks repeatative it is ALOT faster than the for loop
#tag number 1 30% deviation from set means (adjacent cells to this one need to be logged)
result.loc[(result["ResistValue"] <= .70*result["ResistMean"]) | (result["ResistValue"] >= 1.3*result["ResistMean"]), "Tag1"] = "red"
#tag number 2 ambient temp > 30 (current none in our dataset)
result.loc[(result["AmbientTemp"] > 30), "Tag2"] = "red"
#tag number 3 cell > total temp + 3
result.loc[(result["TempValue"] > 3+result["AmbientTemp"]), "Tag3"] = "yellow"
#tag 4 (idk what ripple current is yet)
#result.at[i, "VoltValue"]/result.at[i, "ResistValue"] > .0005*result.at[i, "TotalCurrent"]:

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

app = dash.Dash(__name__, prevent_initial_callbacks=True)

app.layout = html.Div([
    html.Div(
    children=[html.H2("Bart Battery Viewer")],
    style=dict(display='flex', justifyContent='center')
    ),
    html.Div(
    children=[html.Button("Download csv", id="btn"), 
    Download(id="download"),],
    style=dict(display='flex', justifyContent='center')
    ),
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
            options=[{'label': i, 'value': i} for i in ["Tag1", "Tag2", "Tag3", "Tag4"]]),   
        ],style=dict(width='33.33%')),
        #dcc.Dropdown(
        #    id = 'cell', 
        #    options=df.CellNo.unique()),
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
    dcc.Graph(id="graph"),
    html.H2("Errors/Outliers"),
    dash_table.DataTable(
        id = 'table',
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
        df = df[(df["Location"] == Locname) & (df[Tag] != "blue")]
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
        fig = px.scatter(df, x="KeyTime", y=yaxisname, color=Tag, facet_col="CellNo",facet_col_wrap=wrap, height=gheight)
        fig.update_yaxes(matches=None, showticklabels=True)
    return fig

@app.callback(Output("download", "data"), 
    [Input("btn", "n_clicks")])
def generate_csv(n_nlicks):
        df = getdb(conn,cur)
        #can do stuff  to dataframe here
        return send_data_frame(df.to_csv, filename="battdata.csv")

@app.callback([Output('rangeslider', 'max')],
              [Input('Loc', 'value')])
def update_slider(Locname):
    df = getdb(conn,cur)
    df = df[df["Location"] == Locname]
    max = round(int(df["CellNo"].max())),
    return max

@app.callback(Output('range-slider-label', 'children'),
    [Input('rangeslider', 'value')])
def update_output(value):
    return 'Cells {} are selected for viewing'.format(value)

app.run_server(debug=True)