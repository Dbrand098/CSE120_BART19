import pandas as pd
#make sure to backup last baseline incase something goes wrong as the old CurrentBaseline.csv will be rewritten
df = pd.read_csv("newbaselinedata.csv")
df2 = df.groupby(["Location", "CellNo"], as_index=False).mean() #<- made by 6 month data using this call (then do df to csv)
df2.to_csv("CurrentBaseline.csv", index=False)