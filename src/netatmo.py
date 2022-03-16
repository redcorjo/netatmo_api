#!/usr/bin/python3
import requests
import json
import sys
import os
import configparser
import logging
import time
import datetime
import argparse
from enum import Enum
from apscheduler.schedulers.background import BackgroundScheduler
from jinja2 import Template
from netatmo_api import Netatmo_API
from mqtt import MQTT

# logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s',
#     datefmt='%Y-%m-%d:%H:%M:%S',
#     level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#logger.propagate = False

class MyNetatmo():

    settings_file = sys.argv[0].replace(".py", ".ini")
    mqtt = None
    scheduler = None
    all_data = { 
            "homes": [],
            "rooms": [],
            "modules": []
        }

    def __init__(self, settings_file: str = None):
        if settings_file == None:
            self.settings_file = sys.argv[0].replace(".py", ".ini")
        else:
            self.settings_file = settings_file
        config = self.get_settings_file(self.settings_file)
        self.config = config
        # Logging 
        if "severity" in config["logging"]:
            severity = config["logging"]["severity"]
        else:
            severity = "INFO"
        if "filename" in config["logging"]:
            filename = config["logging"]["filename"]
        else:
            filename = None
        if filename == None:
            logging.basicConfig(format='%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', level=severity)
        else:
            logging.basicConfig(format='%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', level=severity, filename=filename)
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
        
        if not os.path.exists(settings_file):
            raise Exception(f"Missing settings file! {settings_file}")
            sys.exit(-1)
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
            config["mqtt"]["topic"] = "netatmo2mqtt"
            config["mqtt"]["broker"] = "127.0.0.1"
            config["mqtt"]["port"] = "1883"
            config["global"] = {}
            config["global"]["frequency"] = "5"
            config["logging"] = {}
            config["logging"]["severity"] = "INFO"
            config["logging"]["filename"] = "netatmo.log"
            with open(settings_file, "w") as config_file:
                config.write(config_file)
        return config

    def background_daemon(self):
        topic = f"{self.topic}/+/+/command"
        self.mqtt.subscribe_topic(topic=topic, on_message=self.mqtt_on_message)

    def schedule_daemon(self):
        if self.scheduler == None:
            self.scheduler = BackgroundScheduler()
        logger.info(f"Schedule daemon with frequency={self.frequency}")
        self.scheduler.add_job(self.get_netatmo_status, "interval", minutes=self.frequency, next_run_time=datetime.datetime.now())
        self.scheduler.start()
        self.background_daemon()

    def mqtt_on_message(self, client, userdata, message):
        if not message.topic.endswith("/state"):
            logger.info(f"message received {message.payload}")
            logger.info(f"message topic={message.topic}")
            logger.info(f"message qos={message.qos}")
            logger.info(f"message retain flag={message.retain}")

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
        all_data = { 
            "homes": [],
            "rooms": [],
            "modules": []
        }
        all_homes = []
        for homedata in homesdata_response["body"]["homes"]:
            my_home_id = homedata["id"]
            if "coordinates" in homedata and "altitude" in homedata:
                homedata["coordinates"] = "{0},{1},{2}".format(homedata["coordinates"][0],homedata["coordinates"][1], homedata["altitude"] )
            all_data["homes"].append(homedata)
            homestatus_response = netatmo.homestatus(home_id=my_home_id)
            if "rooms" in homestatus_response["body"]["home"]:
                for room in homestatus_response["body"]["home"]["rooms"]:
                    item = room["id"]
                    room["home_id"] = my_home_id
                    for home_item in all_data["homes"]:
                        for room_item in home_item["rooms"]:
                            if room["id"] == room_item["id"]:
                                room = {**room , **room_item}
                    if "module_ids" in room:
                        del room["module_ids"]
                    all_data["rooms"].append(room)
                    self.mqtt.send_message(payload=room, item=item)
            else:
                logger.error("Not found any rooms at response")
            if "modules" in homestatus_response["body"]["home"]:
                for module in homestatus_response["body"]["home"]["modules"]:
                    item = module["id"]
                    module["home_id"] = my_home_id
                    for home_item in all_data["homes"]:
                        for module_item in home_item["modules"]:
                            if module["id"] == module_item["id"]:
                                module = {**module, **module_item}
                                module["label"] = module["id"].replace(":", "")
                    if "setup_date" in module:
                        # "yyyy-MM-dd'T'HH:mm:ss.SSSZ"
                        my_formatted_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.localtime(module["setup_date"]))
                        #my_fomratted_time = datetime.datetime.fromtimestamp(module["setup_date"]).strftime('yyyy-MM-dd'T'HH:mm:ssZ')
                        module["setup_date"] = my_formatted_time
                    if "modules_bridged" in module:
                        del module["modules_bridged"]
                    all_data["modules"].append(module)
                    self.mqtt.send_message(payload=module, item=item)
            else:
                logger.error("Not found any modules at response")
            if "rooms" in homedata:
                del homedata["rooms"]
            if "modules" in homedata:
                del homedata["modules"]
            if "schedules" in homedata:
                del homedata["schedules"]
            self.mqtt.send_message(payload=homedata, item=my_home_id)
            all_homes.append(homedata)
        all_data["homes"] = all_homes
        all_data["broker"] = self.broker
        all_data["port"] = self.port
        all_data["topic"] = self.topic
        self.all_data = all_data
        return all_data

    def setthermmode(self, mode="schedule"):
        netatmo = self.get_netatmo_session()
        response = netatmo.setthermmode(mode=mode)
        return response

    def create_openhab_template(self, openhab_basedir="/etc/openhab"):
        logger.info("Creating openhab template file")
        if openhab_basedir.endswith("/"):
            openhab_basedir = openhab_basedir[0:-1]
        template_things_file = "templates/template_things.j2"
        template_items_file = "templates/template_items.j2"
        template_sitemaps_file = "templates/template_sitemaps.j2"
        with open(template_things_file) as my_file:
            template_things = my_file.read()
        with open(template_items_file) as my_file:
            template_items = my_file.read()
        with open(template_sitemaps_file) as my_file:
            template_sitemaps = my_file.read()
        # Template things
        template = Template(template_things)
        data_things = template.render(self.all_data)
        self.create_openhab_file(openhab_basedir, data_things, mode="things")
        # Template items
        template = Template(template_items)
        data_items = template.render(self.all_data)
        self.create_openhab_file(openhab_basedir, data_items, mode="items")
        # Template sitemaps
        template = Template(template_sitemaps)
        data_sitemaps = template.render(self.all_data)
        self.create_openhab_file(openhab_basedir, data_sitemaps, mode="sitemaps")
        return data_things, data_items, data_sitemaps

    def create_openhab_file(self, openhab_basedir, data, mode="things"):
        if mode == "sitemaps":
            extension = "sitemap"
        else:
            extension = mode
        
        target_file = openhab_basedir + "/" + mode + "/netatmo." + extension
        if os.path.exists(openhab_basedir + "/" + mode):
            with open(target_file, "w") as my_file:
                my_file.write(data)
            logger.info(f"Created {target_file}")
        else:
            logger.error(f"openhab basedir {openhab_basedir}/{mode} is not present ")
            return False
        return True

def get_flags():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configfile", type=str, help="init config file")
    parser.add_argument("-st", "--setthermmode", type=str, help="setthermmode away or schedule possible values")
    parser.add_argument("-d", "--daemon", help="daemon", action="store_true")
    parser.add_argument("-oh", "--openhabtemplate", type=str, help="Create openhab template")
    try:
        settings = parser.parse_args()
    except:
        parser.print_help()
        sys.exit(1)
    if len(sys.argv)==1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    return settings
       

def main():
    flags = get_flags()

    positional_args = flags._get_args()
    kw_args = flags._get_kwargs()

    if flags.configfile:
        settings_file = flags.configfile
        logger.info(f"Using alternate config file {settings_file}")
    else:
        settings_file = None

    if flags.setthermmode:
        setthermmode_value = flags.setthermmode
        logger.info(f"sethermmode = {setthermmode_value}")
        valid_options = ["schedule", "away"]
        if setthermmode_value in valid_options:
            netatmo_run = MyNetatmo(settings_file=settings_file)
            response3 = netatmo_run.setthermmode(mode=setthermmode_value)
        else:
            logger.error(f"Use possible values for sethermmode {value_options}")

    if flags.openhabtemplate:
        logger.info("Create Openhab template")
        netatmo_run = MyNetatmo(settings_file=settings_file)
        netatmo_run.get_netatmo_status()
        opehhab_basedir = flags.openhabtemplate
        netatmo_run.create_openhab_template(openhab_basedir=opehhab_basedir)

    if flags.daemon:
        logger.info("Launching daemon")
        netatmo_run = MyNetatmo(settings_file=settings_file)
        netatmo_run.get_netatmo_status()
        netatmo_run.schedule_daemon()
       
    return None


if __name__ == "__main__":
    main()
