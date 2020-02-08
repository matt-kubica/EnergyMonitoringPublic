#!/usr/local/bin/python3

from apscheduler.scheduler import Scheduler
import paho.mqtt.client as mqtt
import time
import logging
import sys
import sqlite3


mqttClientName                                = 'controller'
mqttBrokerHost                                = '0.0.0.0'
mqttUpdateTrigger                             = 'publish'
mqttQos                                       = '2'


sqlitePath                                    = '/home/mateusz/EnergyMonitoring/sqlite/energy_monitoring_config'
scheduleTable                                 = 'controller_schedule'


logFilePath                                   = '/home/mateusz/logs/controller.log'
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
# ------------------------------------------------------------------------------------


class Config():

    def __init__(self, topic, weekday, hour, minute, second):
        self.topic = topic
        self.weekday = weekday
        self.hour = hour
        self.minute = minute
        self.second = second

class Controller():

    def __init__(self):
        self.configList = [] 

        self.scheduler                   = Scheduler()
        self.scheduler.start()
        
        self.uploadConfigList()

        self.mqttClient                  = mqtt.Client(mqttClientName)
        self.mqttClient.on_connect       = onConnect
        self.mqttClient.on_disconnect    = onDisconnect
        self.mqttClient.on_log           = onLog
        self.mqttClient.on_publish       = onPublish
        self.mqttClient.on_message       = onMessage

        self.mqttClient.connect(mqttBrokerHost)
        self.mqttClient.loop_start()    


    def stop(self):
        self.scheduler.shutdown()

        self.mqttClient.loop_stop()
        self.mqttClient.disconnect()


    def uploadConfigList(self):
        tableRows = None
        try:
            tableRows = getTableRows(scheduleTable)
        except sqlite3.Error as err:
            logger.error('SQLite: error: ' + str(err))

        self.configList.clear()
        for row in tableRows:
            config = Config(topic = row[0], weekday = row[1], hour = row[2], minute = row[3], second = row[4])
            logger.info('Uploaded config list with: ' + str(config.topic) + ' ' + str(config.weekday) + ' ' + str(config.hour) + ' ' + str(config.minute) + ' ' + str(config.second))
            self.configList.append(config)
        self.updateScheduler()


    def updateScheduler(self):
        for config in self.configList:
            self.scheduler.add_cron_job(func = self.requestUpdate, args = [config.topic], day_of_week = config.weekday, hour = config.hour, minute = config.minute, second = config.second)


    def requestUpdate(self, mqttTopic):
        self.mqttClient.publish(mqttTopic, mqttUpdateTrigger, int(mqttQos))
    
    

def main():
    
    loggerConfig()

    controller = Controller()
    while(True):
        time.sleep(1)
    controller.stop()


if __name__ == '__main__':
    main()
