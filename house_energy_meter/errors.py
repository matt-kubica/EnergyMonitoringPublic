#!/usr/local/python3

class InfluxUpdaterErrors(Exception):
    # base class
    pass

class SerialError(InfluxUpdaterErrors):
    # raised when there is no connection with serial
    pass

class SQLiteError(InfluxUpdaterErrors):
    # raised when there is no connection with sqlite
    pass

class ModbusError(InfluxUpdaterErrors):
    # raised when there is problem with reading register
    pass

class InfluxError(InfluxUpdaterErrors):
    # raised when there is no connection with influxDB
    pass

class InverterConnectionError(InfluxUpdaterErrors):
    # rasied when there is no connection with inverter
    pass
