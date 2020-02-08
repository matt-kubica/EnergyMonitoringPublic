#!/usr/local/bin/python3.7

import paho.mqtt.client as mqtt
import influxdb as Influx
import time
import errors
import json
import requests
import logging
import sys
import errors


mqttClientName                                = 'inverter'
mqttBrokerHost                                = '0.0.0.0'
mqttSubscribedTopic                           = 'home/energy_monitoring/inverter'
mqttErrorTopic                                = 'home/energy_monitoring/error'
mqttUpdateTrigger                             = 'publish'
mqttQos                                       = '2'


influxDBHost                                  = '0.0.0.0'
influxDBPort                                  = '8086'
influxDBName                                  = 'home_energy_monitoring'
influxDBUser                                  = '******'
influxDBPass                                  = '******'


inverterHost                                  = '178.218.234.100'
inverterPort                                  = '2138'
inverterHostURL                               = 'http://' + inverterHost + ':' + inverterPort + '/home.cgi?sid=0'



APIkey                                        = '9d10bedba49340a28aa0a8664d2ee7f0'
apiURL                                        = 'https://www.zevercloud.com/api/v1/getPlantOverview'
payload                                       = { 'key': APIkey }



logFilePath                                   = '/home/mateusz/logs/inverter.log'
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
        updateInflux()
    except errors.InfluxError as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'InfluxError: ' + str(err)
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    except BaseException as err:
        mqttErrorPayload = str(mqttClientName) + ': ' + 'UnknownError: ' + str(err)
        logger.error('Unknown error: ' + str(err))
        client.publish(mqttErrorTopic, mqttErrorPayload, int(mqttQos))
    else:
        logger.info('Influx updater: Data have been wrote succesfully')
# ------------------------------------------------------------------------------------



def getActiveEnergyAndPower():

    powerAC = 0.0
    energyToday = 0.0
    inverterRequest = None
    try:
        inverterRequest = requests.get(inverterHostURL, timeout = 5)
    except requests.exceptions.ConnectionError:
        logger.warning('Inverter: inactive: cannot connect to inverter')
    else:
        parameterList = list(inverterRequest.text.split('\n'))
        powerAC = float(int(parameterList[10]) / 1000)
        energyToday = float(parameterList[11])


    APIrequest = None
    try:
        APIrequest = requests.get(apiURL, params = payload)
    except requests.exceptions.ConnectionError as err:
        if(APIrequest.status_code != requests.codes.ok):
            logger.error('Inverter: error: cannot connect with zevercloud: ' + str(err))
            raise errors.InverterConnectionError
    else:
        energyTotal = recalculateValues(json.loads(APIrequest.text)['E-Total']['value'], json.loads(APIrequest.text)['E-Total']['unit'])
        return (powerAC, energyToday, energyTotal)


def recalculateValues(value, unit):
    if(unit == 'Wh'):
        value = float(value) / 1000
    elif(unit == 'MWh'):
        value = float(value) * 1000
    elif(unit == 'GWh'):
        value = float(value) * 1000000
    return value
    
        
# influx updater function ------------------------------------------------------------    
def updateInflux():
    client = Influx.InfluxDBClient(host = influxDBHost, port = influxDBPort, username = influxDBUser, password = influxDBPass)
    client.switch_database(influxDBName)

    activePower = None
    activeEnergyProducedToday = None
    activeEnergyProducedTotal = None

    try:
        (activePower, activeEnergyProducedToday, activeEnergyProducedTotal) = getActiveEnergyAndPower()
    except errors.InverterConnectionError:
        pass

    dataPoints = [ {
        'measurement': 'activePower',
        'tags': {
            'device': mqttClientName,
            'dataunit': 'kW'
        },
        'fields': {
            'value': activePower
        }
    },
    {
        'measurement': 'activeEnergyProducedToday',
        'tags': {
            'device': mqttClientName,
            'dataunit': 'kWh'
        },
        'fields': {
            'value': activeEnergyProducedToday
        }
    },
    {
        'measurement': 'activeEnergyProduced',
        'tags': {
            'device': mqttClientName,
            'dataunit': 'kWh'
        },
        'fields': {
            'value': activeEnergyProducedTotal
        }
    } ]
    

        
    if(not client.write_points(dataPoints)):
        logger.error('Influx: error: Cannot write datapoints')
        raise errors.InfluxError
# ------------------------------------------------------------------------------------



# ------------------------------------------------------------------------------------
class Inverter():

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

    inverter = Inverter()
    while(True):
        time.sleep(1)
    inverter.stop()


if __name__ == '__main__':
    main()
