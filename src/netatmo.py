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
logger.propagate = False

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
        topic = f"{self.topic}/#"
        self.mqtt.subscribe_topic(topic=topic)

    def schedule_daemon(self):
        if self.scheduler == None:
            self.scheduler = BackgroundScheduler()
        logger.info(f"Schedule daemon with frequency={self.frequency}")
        self.scheduler.add_job(self.get_netatmo_status, "interval", minutes=self.frequency, next_run_time=datetime.datetime.now())
        self.scheduler.start()
        self.background_daemon()

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
        for homedata in homesdata_response["body"]["homes"]:
            my_home_id = homedata["id"]
            all_data["homes"].append(homedata)
            self.mqtt.send_message(payload=homedata, item=my_home_id)
            homestatus_response = netatmo.homestatus(home_id=my_home_id)
            for room in homestatus_response["body"]["home"]["rooms"]:
                item = room["id"]
                room["home_id"] = my_home_id
                for home_item in all_data["homes"]:
                    for room_item in home_item["rooms"]:
                        if room["id"] == room_item["id"]:
                            room = {**room , **room_item}
                all_data["rooms"].append(room)
                self.mqtt.send_message(payload=room, item=item)
            for module in homestatus_response["body"]["home"]["modules"]:
                item = module["id"]
                module["home_id"] = my_home_id
                for home_item in all_data["homes"]:
                    for module_item in home_item["modules"]:
                        if module["id"] == module_item["id"]:
                            module = {**module, **module_item}
                all_data["modules"].append(module)
                self.mqtt.send_message(payload=module, item=item)
        all_data["broker"] = self.broker
        all_data["port"] = self.port
        all_data["topic"] = self.topic
        self.all_data = all_data
        return all_data

    def setthermmode(self, mode="schedule"):
        netatmo = self.get_netatmo_session()
        response = netatmo.setthermmode(mode=mode)
        return response

    def create_openhab_template(self, opehhab_basedir="/etc/openhab"):
        logger.info("Create opehab template file")
        template_things = """
        Bridge mqtt:broker:mosquitto [ host="{{broker}}", port={{port}}, secure=false ]
{
    // Homes
    {% for my_home in homes -%}
        Thing mqtt:topic:netatmo2mqtthome-{{my_home.id}} "netatmo2mqtt home {{my_home.id}}" {
        Channels:
            Type string   : id "netatmo2mqtt {{my_home.name}} id" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.id"]
            Type string   : name "netatmo2mqtt {{my_home.name}} name" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.name"]
            //Type string   : altitude "netatmo2mqtt {{my_home.name}} altitude" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.altitude"]
            //Type location : coordinates "netatmo2mqtt {{my_home.name}} coordinates" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.coordinates"]
            Type string   : country "netatmo2mqtt {{my_home.name}} country" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.country"]
            Type string   : timezone "netatmo2mqtt {{my_home.name}} timezone" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.timezone"]
            Type string   : temperature_control_mode "netatmo2mqtt {{my_home.name}} temperature_control_mode" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.temperature_control_mode"]
            Type string   : therm_mode "netatmo2mqtt {{my_home.name}} therm_mode" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.therm_mode"]
            Type string   : therm_setpoint_default_duration "netatmo2mqtt {{my_home.name}} therm_setpoint_default_duration" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.therm_setpoint_default_duration"]
            Type string   : cooling_mode "netatmo2mqtt {{my_home.name}} cooling_mode" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.cooling_mode"]
        }

    // Rooms
    {%for room in rooms if room.home_id == my_home.id -%}
        Thing mqtt:topic:netatmo2mqttroom-{{room.id}} "netatmo2mqtt room {{room.name}} home {{my_home.id}}" {
        Channels:
            Type string         : id                          "netatmo2mqtt room {{room.name}} id"                            [ stateTopic="{{topic}}/{{room.id}}/state", transformationPattern="JSONPATH:.id"]
            Type string         : name                        "netatmo2mqtt room {{room.name}} name"                          [ stateTopic="{{topic}}/{{room.name}}/state", transformationPattern="JSONPATH:.name"]
            Type string         : type                        "netatmo2mqtt room {{room.name}} type"                          [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.type"]
            Type switch         : reachable                   "netatmo2mqtt room {{room.name}} reachable"                     [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.reachable"]
            Type switch         : anticipating                "netatmo2mqtt room {{room.name}} anticipating"                  [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.anticipating"]
            Type number         : heating_power_request       "netatmo2mqtt room {{room.name}} heating_power_request"         [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.heating_power_request"]
            Type switch         : open_window                 "netatmo2mqtt room {{room.name}} open_window"                   [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.open_window"]
            Type temperature    : therm_measured_temperature  "netatmo2mqtt room {{room.name}} therm_measured_temperature"    [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.therm_measured_temperature"]
            Type temperature    : therm_setpoint_temperature  "netatmo2mqtt room {{room.name}} therm_setpoint_temperature"    [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.therm_setpoint_temperature"]
            Type temperature    : therm_setpoint_mode         "netatmo2mqtt room {{room.name}} therm_setpoint_mode"           [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.therm_setpoint_mode"]
            Type string         : home_id                     "netatmo2mqtt room {{room.name}} home_id"                       [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.home_id"]
        }
    {% endfor %}

    // Modules
    {%for module in modules if module.home_id == my_home.id  -%}
        Thing mqtt:topic:netatmo2mqttmodule-{{my_home.id}} "netatmo2mqtt module {{module.name}} home {{my_home.id}}" {
        Channels:
            Type string     : id                        "netatmo2mqtt module {{module.name}} id"                                    [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.id"]
            Type string     : type                      "netatmo2mqtt module {{module.name}} type"                                  [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.type"]
            Type string     : name                      "netatmo2mqtt module {{module.name}} name"                                  [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.name"]
            Type string     : setup_date                "netatmo2mqtt module {{module.name}} setup_date"                            [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.setup_date"]
            Type string     : home_id                   "netatmo2mqtt module {{module.name}} home_id"                               [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.home_id"]
            {% if module.type == "NAPlug" %}
            Type string     : setup_date                "netatmo2mqtt module {{module.name}} setup_date"                            [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.setup_date"]
            Type string     : wifi_strength             "netatmo2mqtt module {{module.name}} wifi_strength"                         [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.wifi_strength"]
            {% endif %}
            {% if module.type == "NATherm1" %}
            Type switch     : boiler_valve_comfort_boost            "netatmo2mqtt module {{module.name}} boiler_valve_comfort_boost"                    [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.boiler_valve_comfort_boost"]
            {% endif %}
            {% if module.type != "NAPlug" %}
            Type string     : bridge                    "netatmo2mqtt module {{module.name}} bridge"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.bridge"]
            Type string     : battery_state             "netatmo2mqtt module {{module.name}} battery_state"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.battery_state"]
            Type number     : battery_level             "netatmo2mqtt module {{module.name}} battery_level"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.battery_level"]
            Type string     : firmware_revision         "netatmo2mqtt module {{module.name}} firmware_revision"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.firmware_revision"]
            Type number     : rf_strength               "netatmo2mqtt module {{module.name}} rf_strength"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.rf_strength"]
            Type switch     : reachable                 "netatmo2mqtt module {{module.name}} reachable"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.reachable"]
            Type switch     : boiler_status             "netatmo2mqtt module {{module.name}} boiler_status"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.boiler_status"]
            Type string     : room_id                   "netatmo2mqtt module {{module.name}} room_id"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.room_id"]
            {% endif %}
        }
    {% endfor %}
    {% endfor %}
}
        """
        template = Template(template_things)
        data_things = template.render(self.all_data)
        things_file = opehhab_basedir + "/things/netatmo.things"
        if os.path.exists(opehhab_basedir + "/things"):
            with open(things_file, "w") as my_file:
                my_file.write(data_things)
        else:
            logger.error(f"openhab basedir {openhab_basedir}/things is not present ")
        return data

def get_flags():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--configfile", type=str, help="init config file")
    parser.add_argument("-st", "--setthermmode", type=str, help="setthermmode away or schedule possible values")
    parser.add_argument("-d", "--daemon", help="daemon", action="store_true")
    parser.add_argument("-oh", "--openhabtemplate", help="Create openhab template", action="store_true")

    settings = parser.parse_args()
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
        netatmo_run.create_openhab_template(opehhab_basedir="tmp/openhab")

    if flags.daemon:
        logger.info("Launching daemon")
        netatmo_run = MyNetatmo(settings_file=settings_file)
        netatmo_run.get_netatmo_status()
        netatmo_run.schedule_daemon()
       
    return None


if __name__ == "__main__":
    main()
