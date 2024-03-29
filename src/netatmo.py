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
import datetime
from collections import deque
from enum import Enum
from apscheduler.schedulers.background import BackgroundScheduler
from jinja2 import Template
from netatmo_api import Netatmo_API
from mqtt import MQTT
from web import launch_fastapp

# logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s',
#     datefmt='%Y-%m-%d:%H:%M:%S',
#     level=logging.INFO)
#logger = logging.getLogger(__name__)
#logger.setLevel(logging.INFO)
#logger.propagate = False

logging.basicConfig(level=logging.INFO)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod").lower()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
logging_formatter = logging.Formatter(
    '%(levelname)-8s [%(filename)s:%(lineno)d] (' + ENVIRONMENT + ') - %(message)s')
stream_handler.setFormatter(logging_formatter)
logger.addHandler(stream_handler)
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
    http_port = 8000
    http_host = "0.0.0.0"
    mqtt_receive_queue = deque(maxlen=30)
    mqtt_sent_queue = deque(maxlen=30)
    access_token = None
    refresh_token = None

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
        if "access_token" in config["credentials"]:
            self.access_token = config["credentials"]["access_token"]
        if "refresh_token" in config["credentials"]:
            self.refresh_token = config["credentials"]["refresh_token"]
        if "redirect_uri" in config["credentials"]:
            self.redirect_uri = config["credentials"]["redirect_uri"]
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

        # Settings web server
        if "http" in config:
            if "port" in config["http"]:
                self.http_port = int(config["http"]["port"])
            if "host" in config["http"]:
                self.http_host = int(config["http"]["host"])
                

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
            config["credentials"]["access_token"] = "your_access_token"
            config["credentials"]["refresh_token"] = "your_refresh_token"
            config["credentials"]["redirect_uri"] = "your redirect uri"
            config["credentials"]["scopes"] = "read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach"
            config["home"] = {}
            config["home"]["home_id"] = "your_home_id"
            config["mqtt"] = {}
            config["mqtt"]["topic"] = "netatmo2mqtt"
            config["mqtt"]["broker"] = "127.0.0.1"
            config["mqtt"]["port"] = "1883"
            config["global"] = {}
            config["global"]["frequency"] = "5"
            config["http"] = {}
            config["http"]["port"] = "5"
            config["http"]["host"] = "0.0.0.0"
            config["logging"] = {}
            config["logging"]["severity"] = "INFO"
            config["logging"]["filename"] = "netatmo.log"
            with open(settings_file, "w") as config_file:
                config.write(config_file)
        return config

    def background_daemon(self):
        topic = f"{self.topic}/+/+/command"
        self.mqtt.subscribe_topic(topic=topic, on_message=self.mqtt_on_message)

    def schedule_daemon(self, webserver=False):
        if self.scheduler == None:
            self.scheduler = BackgroundScheduler()
        logger.info(f"Schedule daemon with frequency={self.frequency}")
        self.scheduler.add_job(self.get_netatmo_status, "interval", minutes=self.frequency, next_run_time=datetime.datetime.now())
        if webserver == True:
            logger.info(f"Launch Web server at http://{self.http_host}:{self.http_port}")
            web_config = {
                "config": self.config,
                "instance": self
            }
            web_params = {
                "host": self.http_host,
                "port": self.http_port,
                "settings": web_config
            }
            self.scheduler.add_job(launch_fastapp, kwargs=web_params)
        self.scheduler.start()
        self.background_daemon()

    def mqtt_on_message(self, client, userdata, message):
        if not message.topic.endswith("/state"):
            item = message.topic.split("/")[1]
            topic = message.topic.split("/")[2]
            value = message.payload.decode()
            timestamp = time.time()
            logger.info(f"message received {message.payload} value={value} fulltopic={message.topic} qos={message.qos} flag={message.retain} item={item} topic={topic}")
            payload = {
                "topic": topic,
                "item": item,
                "payload": value,
                "timestamp": timestamp
            }
            self.mqtt_receive_queue.appendleft(payload)
            if topic == "therm_mode":
                self.setthermmode(mode=value)
            if topic == "truetemperature":
                try:
                    self.truetemperature(item, float(value))
                except Exception as e:
                    logger.error("Exception " + str(e))

    def scheduler_status(self):
        return self.scheduler.running

    def get_netatmo_session(self):
        config = self.get_settings_file(self.settings_file)
        netatmo = Netatmo_API(self.client_id, self.client_secret,
                            self.username, self.password, scopes=self.scopes, access_token=self.access_token, redirect_uri=self.redirect_uri, refresh_token=self.refresh_token)
        return netatmo

    def get_netatmo_status(self):
        logger.info("Launching get_netatmo_status")
        # self.mqtt.send_message(payload="test", item="test", topic="test", mode="command")
        netatmo = self.get_netatmo_session()
        homesdata_response = netatmo.homesdata()
        all_data = { 
            "homes": [],
            "rooms": [],
            "modules": []
        }
        all_homes = []
        if homesdata_response != None and "body" in homesdata_response and "homes" in homesdata_response["body"]:
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
                        timestamp = time.time()
                        event = {"topic": "room", "item": item, "payload": room, "timestamp": timestamp}
                        self.mqtt_sent_queue.appendleft(event)
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
                        timestamp = time.time()
                        event = {"topic": "modules", "item": item, "payload": module, "timestamp": timestamp}
                        self.mqtt_sent_queue.appendleft(event)
                        self.mqtt.send_message(payload=module, item=item)
                else:
                    logger.error("Not found any modules at response")
                if "rooms" in homedata:
                    del homedata["rooms"]
                if "modules" in homedata:
                    del homedata["modules"]
                if "schedules" in homedata:
                    del homedata["schedules"]
                timestamp = time.time()
                event = event = {"topic": "homedata", "item": my_home_id, "payload": homedata, "timestamp": timestamp}
                self.mqtt_sent_queue.appendleft(event)
                self.mqtt.send_message(payload=homedata, item=my_home_id)
                all_homes.append(homedata)
        else:
            logger.warning("No homesdata_response obtained")
        all_data["homes"] = all_homes
        all_data["broker"] = self.broker
        all_data["port"] = self.port
        all_data["topic"] = self.topic
        self.all_data = all_data
        return all_data

    def setthermmode(self, mode="schedule"):
        logger.info(f"Triggered setthermmode mode={mode}")
        netatmo = self.get_netatmo_session()
        response = netatmo.setthermmode(mode=mode)
        return response

    def truetemperature(self, room_id: str, corrected_temperature: float, home_id: str = None):
        logger.info(f"Triggered truetemperature room_id={room_id} corrected_temperature={corrected_temperature}")
        netatmo = self.get_netatmo_session()
        response = netatmo.set_truetemperature(room_id, corrected_temperature, home_id)
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
    parser.add_argument("-web", "--webserver", help="web server", action="store_true")
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
            logger.error(f"Use possible values for sethermmode {valid_options}")

    if flags.openhabtemplate:
        logger.info("Create Openhab template")
        netatmo_run = MyNetatmo(settings_file=settings_file)
        netatmo_run.get_netatmo_status()
        opehhab_basedir = flags.openhabtemplate
        netatmo_run.create_openhab_template(openhab_basedir=opehhab_basedir)

    if flags.webserver:
        webserver = True
    else:
        webserver = False

    if flags.daemon:
        logger.info("Launching daemon")
        netatmo_run = MyNetatmo(settings_file=settings_file)
        netatmo_run.get_netatmo_status()
        netatmo_run.schedule_daemon(webserver=webserver)
       
    return None


if __name__ == "__main__":
    main()
