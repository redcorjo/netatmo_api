#!/bin/python3
import requests
import json
import sys
import os
import configparser
import logging
import time
import argparse
from apscheduler.schedulers.background import BackgroundScheduler
from netatmo_api import Netatmo_API
from mqtt import MQTT

logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.propagate = False

class MyNetatmo():

    settings_file = sys.argv[0].replace(".py", ".ini")
    mqtt = None
    scheduler = None

    def __init__(self, settings_file: str = None):
        if settings_file == None:
            self.settings_file = sys.argv[0].replace(".py", ".ini")
        else:
            self.settings_file = settings_file
        config = self.get_settings_file(self.settings_file)
        self.config = config
        # Credentials
        self.client_id = config["credentials"]["client_id"]
        self.client_secret = config["credentials"]["client_secret"]
        self.username = config["credentials"]["username"]
        self.password = config["credentials"]["password"]
        try:
            self.scopes = config["credentials"]["scopes"]
        except:
            self.scopes = None

        # Settings home section
        self.home_id = config["home"]["home_id"]

        # Settings mqtt
        self.topic =  config["mqtt"]["topic"]
        self.broker = config["mqtt"]["broker"]
        self.port  = int(config["mqtt"]["port"])
        self.mqtt_settings = {
            "topic": self.topic,
            "broker": self.broker,
            "port": self.port
        }
        self.mqtt = MQTT(**self.mqtt_settings )

        # Settings scheduler
        self.frequency = int(config["global"]["frequency"])

    def get_settings_file(self, settings_file: str = None):
        if settings_file == None:
            settings_file = self.settings_file
        config = configparser.ConfigParser()
        config.read(settings_file)

        if config.sections() == []:
            logger.warning(
                f"Created settings file {settings_file} with template data")
            config["credentials"] = {}
            config["credentials"]["client_id"] = "your_client_id"
            config["credentials"]["client_secret"] = "your_client_secret"
            config["credentials"]["username"] = "your_username"
            config["credentials"]["password"] = "your_password"
            config["credentials"]["scopes"] = "read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach"
            config["home"] = {}
            config["home"]["home_id"] = "your_home_id"
            config["mqtt"] = {}
            config["mqtt"]["topic"] = "netatmo2mqtt/status"
            config["mqtt"]["broker"] = "127.0.0.1"
            config["mqtt"]["port"] = "1883"
            config["global"] = {}
            config["global"]["frequency"] = "5"
            with open(settings_file, "w") as config_file:
                config.write(config_file)
        return config

    def schedule_daemon(self):
        if self.scheduler == None:
            self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(self.get_netatmo_status, "interval", minutes=self.frequency)
        self.scheduler.start()

    def scheduler_status(self):
        return self.scheduler.running

    def get_netatmo_session(self):
        config = self.get_settings_file(self.settings_file)
        netatmo = Netatmo_API(self.client_id, self.client_secret,
                            self.username, self.password, scopes=self.scopes)
        return netatmo

    def get_netatmo_status(self):
        logger.info("Launching get_netatmo_status")
        netatmo = self.get_netatmo_session()
        homesdata_response = netatmo.homesdata()
        for homedata in homesdata_response["body"]["homes"]:
            my_home_id = homedata["id"]
            self.mqtt.send_message(payload=homedata, item=my_home_id)
            homestatus_response = netatmo.homestatus(home_id=my_home_id)
            for room in homestatus_response["body"]["home"]["rooms"]:
                item = room["id"]
                self.mqtt.send_message(payload=room, item=item)
            for module in homestatus_response["body"]["home"]["modules"]:
                item = module["id"]
                self.mqtt.send_message(payload=module, item=item)
        return None

    def setthermmode(self, mode="schedule"):
        netatmo = self.get_netatmo_session()
        response = netatmo.setthermmode(mode=mode)
        return response

def get_flags():
    # parser = argparse.ArgumentParser()
    # parser.add_argument()("-c", "--configfile", help="init config file", required=False)
    # parser.add_argument()("-d", "--daemon", help="daemon", required=False)

    # settings = parser.parse_args()
    settings = None
    return settings
       

def main():
    flags = get_flags()

    if len(sys.argv) > 0:
        parameter = sys.argv[1]
    else:
        parameter = "schedule"

    netatmo_run = MyNetatmo()
    netatmo_run.get_netatmo_status()
    netatmo_run.schedule_daemon()
    while netatmo_run.scheduler_status():
        time.sleep(10)
    response3 = netatmo_run.setthermmode(mode=parameter)
       
    return None


if __name__ == "__main__":
    main()
