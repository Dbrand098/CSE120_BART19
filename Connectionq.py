#this code is to conenct to mariadb through python
#mariaDB must already be running and login information is needed
#this code is currently not tested for nonlocal server

import mariadb
import sys

#connecting to db server
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

# Get Cursor to interface with db
cur = conn.cursor()

query = "whatever you want to query from the db"

#execute the query
cur.execute(query)

#Getting data off the cursor
test = cur.fetchall()  #this is made up of all tuples so itll need to be looped through or put in some type of datatype

