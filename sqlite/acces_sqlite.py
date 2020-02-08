#!/usr/local/python3.7

import sqlite3
from sqlite3 import Error

connection = None
try:
    connection = sqlite3.connect('/home/pi/sqlite_databases/energy_monitoring_config')
except Error as error:
    print(error)
    exit()

cursor = connection.cursor()
cursor.execute('SELECT * FROM sdm630_registers')
rows = cursor.fetchall()

for r in rows:
    print(r)


