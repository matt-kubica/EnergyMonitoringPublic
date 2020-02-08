#!/usr/local/bin/python3.7

import paho.mqtt.client as mqtt
import influxdb as Influx
import minimalmodbus
import serial
import time
import sqlite3
import errors
import logging
import sys


mqttClientName                                = 'main_energy_meter'
mqttBrokerHost                                = '0.0.0.0'
mqttSubscribedTopic                           = 'home/energy_monitoring/main_energy_meter'
mqttErrorTopic                                = 'home/energy_monitoring/error'
mqttUpdateTrigger                             = 'publish'
mqttQos                                       = '2'


influxDBHost                                  = '0.0.0.0'
influxDBPort                                  = '8086'
influxDBName                                  = 'home_energy_monitoring'
influxDBUser                                  = '******'
influxDBPass                                  = '******'


serialPortName                                = '/dev/ttyAMA0'
slaveaddress                                  = '1'


sqlitePath                                    = '/home/pi/EnergyMonitoring/sqlite/energy_monitoring_config'
registersTableName                            = 'sdm630_registers'


logFilePath                                   = '/home/pi/logs/main_energy_meter.log'
logger                                        = None



# logger config -------------------------------------------------------------------
def loggerConfig():
    global logger
    logger = logging.getLogger(__name__)

    fileHandler = logging.FileHandler(logFilePath)
    streamHandler = logging.StreamHandler(sys.stdout)

    formatter = logging.Formatter('%(asctime)s\t%(filename)s\t%(levelname)s\t%(message)s')
    
    fileHandler.setFormatter(formatter)
    streamHandler.setFormatter(formatter)

    logger.addHandler(fileHandler)
    logger.addHandler(streamHandler)
    logger.setLevel(logging.INFO)
# ----------------------------------------------------------------------------------



# class for readings from energy meter ---------------------------------------------
class EnergyMeter(minimalmodbus.Instrument):

    def __init__(self, portname, slaveaddress = 1, baudrate = 9600, parity = serial.PARITY_EVEN, timeout = 0.1):
        minimalmodbus.Instrument.__init__(self, portname, slaveaddress)
        self.serial.parity = parity
        self.serial.baudrate = baudrate
        self.serial.timeout = timeout


    def getRegisterData(self, address, datatype, functioncode = 3):
        if(datatype == 'float'):
            return self.read_float(address, functioncode = functioncode)
        elif(datatype == 'int'):
            return self.read_register(address, functioncode = functioncode)
        elif(datatype == 'long'):
            return self.read_long(address, functioncode = functinocode)
        else:
            raise TypeError


    def changeRegisterData(self, address, datatype, newValue):
        if(datatype == 'float'):
            self.write_float(address, float(newValue))
        elif(datatype == 'int'):
            self.write_register(address, int(newValue))
        elif(datatype == 'long'):
            self.write_long(address, int(newValue))
        else:
            raise TypeError
# ------------------------------------------------------------------------------------



# function for sqlite acces ----------------------------------------------------------    
def getTableRows(tableName):
    connection = sqlite3.connect(sqlitePath)
    cursor = connection.cursor()
    cursor.execute('SELECT * FROM ' + str(tableName))
    return cursor.fetchall()
# ------------------------------------------------------------------------------------



# mqtt callbacks ---------------------------------------------------------------------
def onLog(client, userdata, level, buf):
    logger.info('MQTT callback: on_log: ' + str(buf))


def onConnect(client, userdata, flags, rc):
    if(rc == 0):
        logger.info('MQTT callback: on_connect: Connection OK...')
    else:
        logger.info('MQTT callback: on_connect: Bad connection, returned code: ' + str(rc))


def onDisconnect(client, userdata, flags, rc = 0):
    logger.info('MQTT callback: on_disconnect: Disconnected with result code: ' + str(rc))


def onPublish(client, userdata, result):
    logger.info('MQTT callback: on_publish: Data published...')
    pass


def onMessage(client, userdata, message):
    logger.info('MQTT callback: on_message: Message topic: ' + str(message.topic))
    logger.info('MQTT callback: on_message: Message qos: ' + str(message.qos))
    logger.info('MQTT callback: on_message: Message payload: ' + str(message.payload))

    try:
        updateInflux(serialPortName, registersTableName)
    except errors.InfluxError as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'InfluxError: ' + str(err)
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    except errors.SerialError as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'SerialError: ' + str(err)
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    except errors.SQLiteError as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'SQLiteError: ' + str(err)
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    except errors.ModbusError as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'ModbusError: ' + str(err)
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    except BaseException as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'UnknownError: ' + str(err)
        logger.error('Unknown error: ' + str(err))
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    else:
        logger.info('Influx updater: Data have been wrote succesfully')
# ------------------------------------------------------------------------------------
            
    
        
# influx updater function ------------------------------------------------------------    
def updateInflux(portname, registersTable):
    client = Influx.InfluxDBClient(host = influxDBHost, port = influxDBPort, username = influxDBUser, password = influxDBPass)
    client.switch_database(influxDBName)

    modbusErrorCounter = 0
    energyMeter = None
    dataPointsList = []
    tableRows = None

    try:
        energyMeter = EnergyMeter(portname, slaveaddress = int(slaveaddress), parity = serial.PARITY_NONE)
    except:
        logger.error('Serial: exception: cannot connect with serial port ' + str(portname))
        raise errors.SerialError

    try:
        tableRows = getTableRows(registersTable)
    except sqlite3.Error as err:
        logger.error('SQLite: error: ' + str(err))
        raise errors.SQLiteError


    for row in tableRows:
        value = None
        try:
            value = energyMeter.getRegisterData(row[0], row[3], functioncode = row[4])     # arguments (address, datatype, functioncode) 
        except (IOError, ValueError, IndexError, TypeError) as exc:
            logger.error('Modbus: exception: during reading register ' + str(row[0]) + ': ' + str(exc))
            modbusErrorCounter += 1
            continue
            
        measurement = row[1]
        dataunit = row[2]

        dataPoint = {
            'measurement': str(measurement),
            'tags': {
                'device': mqttClientName,
                'dataunit': str(dataunit)
            },
            "fields": {
                'value': value
            }
        } 
        dataPointsList.append(dataPoint)

        
    if(not client.write_points(dataPointsList)):
        logger.error('Influx: error: Cannot write datapoints')
        raise errors.InfluxError

    if(modbusErrorCounter != 0):
        raise errors.ModbusError
# ------------------------------------------------------------------------------------



# ------------------------------------------------------------------------------------
class HouseEnergyMeter():

    def __init__(self):

        self.mqttClient                  = mqtt.Client(mqttClientName)
        self.mqttClient.on_connect       = onConnect
        self.mqttClient.on_disconnect    = onDisconnect
        self.mqttClient.on_log           = onLog
        self.mqttClient.on_publish       = onPublish
        self.mqttClient.on_message       = onMessage

        self.mqttClient.connect(mqttBrokerHost)
        self.mqttClient.loop_start()
        self.mqttClient.subscribe(mqttSubscribedTopic, int(mqttQos))    


    def stop(self):
        self.mqttClient.loop_stop()
        self.mqttClient.disconnect()
# ------------------------------------------------------------------------------------

    

def main():
    
    loggerConfig()

    houseEnergyMeter = HouseEnergyMeter()
    while(True):
        time.sleep(1)
    houseEnergyMeter.stop()


if __name__ == '__main__':
    main()
