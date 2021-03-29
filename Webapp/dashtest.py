import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
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
    
def getdb(conn,cur):

    query = "select KeyTime, Location, CellNo, VoltValue, ResistValue, TempValue from history.cells, info.bankinfo where info.bankinfo.BankId = history.cells.BankId order by Location"

    df1 = pd.read_sql_query(query, conn)

    df2 = pd.read_csv("testmean.csv")
    #df2 = df.groupby(["Location", "CellNo"], as_index=False).mean()
    df2.columns = ["Location", "CellNo","VoltMean", "ResistMean", "TempMean"]

    result = pd.merge(df1, df2, on=["Location","CellNo"])

    #tagging should be done on backend
    result["Tag"] = "blue"
    result.loc[(result["ResistValue"] <= .70*result["ResistMean"]) | (result["ResistValue"] >= 1.3*result["ResistMean"]), "Tag"] = "red"
    return result

df = getdb(conn,cur)

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("Bart Battery Viewer"),
    dcc.Dropdown(
        id = 'Loc', 
        options=[{'label': i, 'value': i} for i in df.Location.unique()]),
    dcc.Dropdown(
        id = 'yaxis', 
        options=[{'label': i, 'value': i} for i in list(df)]),    
    #dcc.Dropdown(
    #    id = 'cell', 
    #    options=df.CellNo.unique()),
    dcc.Graph(id="graph", style={'width': '180vh', 'height': '180vh'}),
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
    [Input('Loc', 'value')])
def updateTable(Locname):
    if Locname != None:
        df = getdb(conn,cur) 
        #might wanna change to contains
        df = df[(df["Location"] == Locname) & (df["Tag"] == "red")]
        col = [{"name": i, "id": i} for i in list(df.columns)]
        return df.to_dict('records'), col
    return [],[]

@app.callback(
    Output("graph", "figure"), 
    [Input("Loc", "value"),
    Input("yaxis", "value"),])
def update_graph(Locname, yaxisname):
    wrap = 6
    fig = go.Figure()
    if Locname != None and yaxisname != None:
        df = getdb(conn,cur)
        df = df[df["Location"] == Locname]
        if Locname == "Daly City Station":
            wrap = 18
        fig = px.scatter(df, x="KeyTime", y=yaxisname, color='Tag', facet_col="CellNo",facet_col_wrap=wrap)
        fig.update_yaxes(matches=None, showticklabels=True)
    return fig

app.run_server(debug=True)