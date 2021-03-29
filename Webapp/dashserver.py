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
#tag number 1 30% deviation from set means
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

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H2("Bart Battery Viewer"),
    dcc.Dropdown(
        id = 'Loc', 
        options=[{'label': i, 'value': i} for i in df.Location.unique()]),
    dcc.Dropdown(
        id = 'yaxis', 
        options=[{'label': i, 'value': i} for i in list(df)]),
    dcc.Dropdown(
        id = 'Tags', 
        options=[{'label': i, 'value': i} for i in ["Tag1", "Tag2", "Tag3", "Tag4"]]),      
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
    [Input('Loc', 'value'),
    Input('Tags', 'value')])
def updateTable(Locname, Tag):
    if Locname != None and Tag != None:
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
    Input('Tags', 'value')])
def update_graph(Locname, yaxisname, Tag):
    wrap = 6
    fig = go.Figure()
    if Locname != None and yaxisname != None and Tag != None:
        df = getdb(conn,cur)
        df = df[df["Location"] == Locname]
        if Locname == "Daly City Station":
            wrap = 18
        fig = px.scatter(df, x="KeyTime", y=yaxisname, color=Tag, facet_col="CellNo",facet_col_wrap=wrap)
        fig.update_yaxes(matches=None, showticklabels=True)
    return fig

app.run_server(debug=True)