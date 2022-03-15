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
                            module["label"] = module["id"].replace(":", "")
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

    def create_openhab_template(self, openhab_basedir="/etc/openhab"):
        logger.info("Creating openhab template file")
        if openhab_basedir.endswith("/"):
            openhab_basedir = openhab_basedir[0:-1]
        template_things = """
        Bridge mqtt:broker:netatmo [ host="{{broker}}", port={{port}}, secure=false ]
{
    // Homes
    {% for my_home in homes -%}
        Thing mqtt:topic:netatmohome{{my_home.id}} "netatmo2mqtt home {{my_home.id}}" {
        Channels:
            Type string   : id "netatmo2mqtt {{my_home.name}} id" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.id"]
            Type string   : name "netatmo2mqtt {{my_home.name}} name" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.name"]
            Type number   : altitude "netatmo2mqtt {{my_home.name}} altitude" [ stateTopic="{{topic}}/{{my_home.id}}/state", transformationPattern="JSONPATH:.altitude"]
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
        Thing mqtt:topic:netatmoroom{{room.id}} "netatmo2mqtt room {{room.name}} home {{my_home.id}}" {
        Channels:
            Type string         : id                          "netatmo2mqtt room {{room.name}} id"                            [ stateTopic="{{topic}}/{{room.id}}/state", transformationPattern="JSONPATH:.id"]
            Type string         : name                        "netatmo2mqtt room {{room.name}} name"                          [ stateTopic="{{topic}}/{{room.name}}/state", transformationPattern="JSONPATH:.name"]
            Type string         : type                        "netatmo2mqtt room {{room.name}} type"                          [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.type"]
            Type switch         : reachable                   "netatmo2mqtt room {{room.name}} reachable"                     [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.reachable",on="true", off="false"]
            Type switch         : anticipating                "netatmo2mqtt room {{room.name}} anticipating"                  [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.anticipating",on="true", off="false"]
            Type number         : heating_power_request       "netatmo2mqtt room {{room.name}} heating_power_request"         [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.heating_power_request"]
            Type switch         : open_window                 "netatmo2mqtt room {{room.name}} open_window"                   [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.open_window",on="true", off="false"]
            Type number         : therm_measured_temperature  "netatmo2mqtt room {{room.name}} therm_measured_temperature"    [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.therm_measured_temperature"]
            Type number         : therm_setpoint_temperature  "netatmo2mqtt room {{room.name}} therm_setpoint_temperature"    [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.therm_setpoint_temperature"]
            Type number         : therm_setpoint_mode         "netatmo2mqtt room {{room.name}} therm_setpoint_mode"           [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.therm_setpoint_mode"]
            Type string         : home_id                     "netatmo2mqtt room {{room.name}} home_id"                       [ stateTopic="{{topic}}/{{room.type}}/state", transformationPattern="JSONPATH:.home_id"]
        }
    {% endfor %}

    // Modules
    {%for module in modules if module.home_id == my_home.id  -%}
        Thing mqtt:topic:netatmomodule{{module.label}} "netatmo2mqtt module {{module.name}} home {{my_home.id}}" {
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
            Type switch     : boiler_valve_comfort_boost            "netatmo2mqtt module {{module.name}} boiler_valve_comfort_boost"                    [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.boiler_valve_comfort_boost",on="true", off="false"]
            {% endif %} 
            {% if module.type != "NAPlug" %}
            Type string     : bridge                    "netatmo2mqtt module {{module.name}} bridge"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.bridge"]
            Type string     : battery_state             "netatmo2mqtt module {{module.name}} battery_state"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.battery_state"]
            Type number     : battery_level             "netatmo2mqtt module {{module.name}} battery_level"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.battery_level"]
            Type string     : firmware_revision         "netatmo2mqtt module {{module.name}} firmware_revision"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.firmware_revision"]
            Type number     : rf_strength               "netatmo2mqtt module {{module.name}} rf_strength"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.rf_strength"]
            Type switch     : reachable                 "netatmo2mqtt module {{module.name}} reachable"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.reachable",on="true", off="false"]
            Type switch     : boiler_status             "netatmo2mqtt module {{module.name}} boiler_status"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.boiler_status",on="true", off="false"]
            Type string     : room_id                   "netatmo2mqtt module {{module.name}} room_id"                                [ stateTopic="{{topic}}/{{module.id}}/state", transformationPattern="JSONPATH:.room_id"]
            {% endif %}
        }
    {% endfor %}
    {% endfor %}
}
        """
        template_items="""
    // Homes
    {% for my_home in homes -%}
            String netatmo_home_{{my_home.id}}_id                               "netatmo2mqtt {{my_home.name}} id"                              { channel="mqtt:topic:netatmohome{{my_home.id}}:id"}
            String netatmo_home_{{my_home.id}}_name                             "netatmo2mqtt {{my_home.name}} name"                            { channel="mqtt:topic:netatmohome{{my_home.id}}:name"}
            Number netatmo_home_{{my_home.id}}_altitude                         "netatmo2mqtt {{my_home.name}} altitude"                        { channel="mqtt:topic:netatmohome{{my_home.id}}:altitude"}
            Location netatmo_home_{{my_home.id}}_coordinates                    "netatmo2mqtt {{my_home.name}} coordinates [%2$s°N %3$s°E]"     { channel="mqtt:topic:netatmohome{{my_home.id}}:coordinates"}
            String netatmo_home_{{my_home.id}}_country                          "netatmo2mqtt {{my_home.name}} country"                         { channel="mqtt:topic:netatmohome{{my_home.id}}:country"}
            String netatmo_home_{{my_home.id}}_timezone                         "netatmo2mqtt {{my_home.name}} timezone"                        { channel="mqtt:topic:netatmohome{{my_home.id}}:timezone"}
            String netatmo_home_{{my_home.id}}_temperature_control_mode         "netatmo2mqtt {{my_home.name}} temperature_control_mode"        { channel="mqtt:topic:netatmohome{{my_home.id}}:temperature_control_mode"}
            String netatmo_home_{{my_home.id}}_therm_mode                       "netatmo2mqtt {{my_home.name}} therm_mode"                      { channel="mqtt:topic:netatmohome{{my_home.id}}:therm_mode"}
            Number netatmo_home_{{my_home.id}}_therm_setpoint_default_duration  "netatmo2mqtt {{my_home.name}} therm_setpoint_default_duration" { channel="mqtt:topic:netatmohome{{my_home.id}}:therm_setpoint_default_duration"}
            String netatmo_home_{{my_home.id}}_cooling_mode                     "netatmo2mqtt {{my_home.name}} cooling_mode"                    { channel="mqtt:topic:netatmohome{{my_home.id}}:cooling_mode"}

    // Rooms
    {%for room in rooms if room.home_id == my_home.id -%}
            String netatmo_room_{{room.id}}_id                          "netatmo2mqtt room {{room.name}} id"                                               { channel="mqtt:topic:netatmoroom{{room.id}}:id"}
            String netatmo_room_{{room.id}}_name                        "netatmo2mqtt room {{room.name}} name"                                             { channel="mqtt:topic:netatmoroom{{room.id}}:name"}
            String netatmo_room_{{room.id}}_type                        "netatmo2mqtt room {{room.name}} type"                                             { channel="mqtt:topic:netatmoroom{{room.id}}:type"}
            Switch netatmo_room_{{room.id}}_reachable                   "netatmo2mqtt room {{room.name}} reachable"                                        { channel="mqtt:topic:netatmoroom{{room.id}}:reachable"}
            Switch netatmo_room_{{room.id}}_anticipating                "netatmo2mqtt room {{room.name}} anticipating"                                     { channel="mqtt:topic:netatmoroom{{room.id}}:anticipating"}
            Number netatmo_room_{{room.id}}_heating_power_request       "netatmo2mqtt room {{room.name}} heating_power_request"                            { channel="mqtt:topic:netatmoroom{{room.id}}:heating_power_request"}
            Switch netatmo_room_{{room.id}}_open_window                 "netatmo2mqtt room {{room.name}} open_window"  <contact>                           { channel="mqtt:topic:netatmoroom{{room.id}}:open_window"}
            Number netatmo_room_{{room.id}}_therm_measured_temperature  "netatmo2mqtt room {{room.name}} therm_measured_temperature [%.2f °C]" <temp>      { channel="mqtt:topic:netatmoroom{{room.id}}:therm_measured_temperature"}
            Number netatmo_room_{{room.id}}_therm_setpoint_temperature  "netatmo2mqtt room {{room.name}} therm_setpoint_temperature [%.2f °C]" <temp>      { channel="mqtt:topic:netatmoroom{{room.id}}:therm_setpoint_temperature"}
            String netatmo_room_{{room.id}}_therm_setpoint_mode         "netatmo2mqtt room {{room.name}} therm_setpoint_mode"                              { channel="mqtt:topic:netatmoroom{{room.id}}:therm_setpoint_mode"}
            String netatmo_room_{{room.id}}_home_id                     "netatmo2mqtt room {{room.name}} home_id"                                          { channel="mqtt:topic:netatmoroom{{room.id}}:home_id"}
    {% endfor %}

    // Modules
    {%for module in modules if module.home_id == my_home.id  -%}
            String netatmo_module_{{module.label}}_id                        "netatmo2mqtt module {{module.name}} id"                                           { channel="mqtt:topic:netatmomodule{{module.label}}:id"}
            String netatmo_module_{{module.label}}_type                      "netatmo2mqtt module {{module.name}} type"                                         { channel="mqtt:topic:netatmomodule{{module.label}}:type"}
            String netatmo_module_{{module.label}}_name                      "netatmo2mqtt module {{module.name}} name"            <radiator>                   { channel="mqtt:topic:netatmomodule{{module.label}}:name"}
            Number netatmo_module_{{module.label}}_setup_date                "netatmo2mqtt module {{module.name}} setup_date"                                   { channel="mqtt:topic:netatmomodule{{module.label}}:setup_date"}
            String netatmo_module_{{module.label}}_home_id                   "netatmo2mqtt module {{module.name}} home_id"                                      { channel="mqtt:topic:netatmomodule{{module.label}}:home_id"}
            {% if module.type == "NAPlug" %}
            //netatmo_module_{{module.label}}_setup_date                "netatmo2mqtt module {{module.name}} setup_date"                                        { channel="mqtt:topic:netatmomodule{{module.label}}:setup_date"}
            Number netatmo_module_{{module.label}}_wifi_strength             "netatmo2mqtt module {{module.name}} wifi_strength"                                { channel="mqtt:topic:netatmomodule{{module.label}}:wifi_strength"}
            {% endif %}
            {% if module.type == "NATherm1" %}
            Switch netatmo_module_{{module.label}}_boiler_valve_comfort_boost "netatmo2mqtt module {{module.name}} boiler_valve_comfort_boost"                  { channel="mqtt:topic:netatmomodule{{module.label}}:boiler_valve_comfort_boost"}
            {% endif %}
            {% if module.type != "NAPlug" %}
            String netatmo_module_{{module.label}}_bridge                    "netatmo2mqtt module {{module.name}} bridge"                                       { channel="mqtt:topic:netatmomodule{{module.label}}:bridge"}
            String netatmo_module_{{module.label}}_battery_state             "netatmo2mqtt module {{module.name}} battery_state"    <battery>                   { channel="mqtt:topic:netatmomodule{{module.label}}:battery_state"}
            Number netatmo_module_{{module.label}}_battery_level             "netatmo2mqtt module {{module.name}} battery_level"    <batterylevel>              { channel="mqtt:topic:netatmomodule{{module.label}}:battery_level"}
            String netatmo_module_{{module.label}}_firmware_revision         "netatmo2mqtt module {{module.name}} firmware_revision"                            { channel="mqtt:topic:netatmomodule{{module.label}}:firmware_revision"}
            Number netatmo_module_{{module.label}}_rf_strength               "netatmo2mqtt module {{module.name}} rf_strength"     <network>                    { channel="mqtt:topic:netatmomodule{{module.label}}:rf_strength"}
            Switch netatmo_module_{{module.label}}_reachable                 "netatmo2mqtt module {{module.name}} reachable"                                    { channel="mqtt:topic:netatmomodule{{module.label}}:reachable"}
            Switch netatmo_module_{{module.label}}_boiler_status             "netatmo2mqtt module {{module.name}} boiler_status"   <heating>                    { channel="mqtt:topic:netatmomodule{{module.label}}:boiler_status"}
            Number netatmo_module_{{module.label}}_room_id                   "netatmo2mqtt module {{module.name}} room_id"                                      { channel="mqtt:topic:netatmomodule{{module.label}}:room_id"}
            {% endif %}
    {% endfor %}
    {% endfor %}
        """
        template_sitemaps="""
    sitemap netatmo label="Netatmo" {
    // Homes
    {% for my_home in homes -%}
            Frame 
            {
                Text label="Home {{my_home.id}}" 
                {
                    Default item=netatmo_home_{{my_home.id}}_id                               label="netatmo2mqtt {{my_home.name}} id"                        
                    Default item=netatmo_home_{{my_home.id}}_name                             label="netatmo2mqtt {{my_home.name}} name"                           
                    Default item=netatmo_home_{{my_home.id}}_altitude                         label="netatmo2mqtt {{my_home.name}} altitude"                       
                    Default item=netatmo_home_{{my_home.id}}_coordinates                      label="netatmo2mqtt {{my_home.name}} coordinates [%2$s°N %3$s°E]"    
                    Default item=netatmo_home_{{my_home.id}}_country                          label="netatmo2mqtt {{my_home.name}} country"                        
                    Default item=netatmo_home_{{my_home.id}}_timezone                         label="netatmo2mqtt {{my_home.name}} timezone"                       
                    Default item=netatmo_home_{{my_home.id}}_temperature_control_mode         label="netatmo2mqtt {{my_home.name}} temperature_control_mode"       
                    Default item=netatmo_home_{{my_home.id}}_therm_mode                       label="netatmo2mqtt {{my_home.name}} therm_mode"                     
                    Default item=netatmo_home_{{my_home.id}}_therm_setpoint_default_duration  label="netatmo2mqtt {{my_home.name}} therm_setpoint_default_duration"
                    Default item=netatmo_home_{{my_home.id}}_cooling_mode                     label="netatmo2mqtt {{my_home.name}} cooling_mode"                   
                }
            }

    // Rooms
    {%for room in rooms if room.home_id == my_home.id -%}
            Frame {
                Text label="Room {{room.name}}"
                {
                    Default item=netatmo_room_{{room.id}}_id                          label="netatmo2mqtt room {{room.name}} id"                                               
                    Default item=netatmo_room_{{room.id}}_name                        label="netatmo2mqtt room {{room.name}} name"                                             
                    Default item=netatmo_room_{{room.id}}_type                        label="netatmo2mqtt room {{room.name}} type"                                             
                    Default item=netatmo_room_{{room.id}}_reachable                   label="netatmo2mqtt room {{room.name}} reachable"                                        
                    Default item=netatmo_room_{{room.id}}_anticipating                label="netatmo2mqtt room {{room.name}} anticipating"                                     
                    Default item=netatmo_room_{{room.id}}_heating_power_request       label="netatmo2mqtt room {{room.name}} heating_power_request"                            
                    Default item=netatmo_room_{{room.id}}_open_window                 label="netatmo2mqtt room {{room.name}} open_window"                            
                    Default item=netatmo_room_{{room.id}}_therm_measured_temperature  label="netatmo2mqtt room {{room.name}} therm_measured_temperature [%.2f °C]" 
                    Default item=netatmo_room_{{room.id}}_therm_setpoint_temperature  label="netatmo2mqtt room {{room.name}} therm_setpoint_temperature [%.2f °C]"       
                    Default item=netatmo_room_{{room.id}}_therm_setpoint_mode         label="netatmo2mqtt room {{room.name}} therm_setpoint_mode"                              
                    Default item=netatmo_room_{{room.id}}_home_id                     label="netatmo2mqtt room {{room.name}} home_id"                                          
                }
            }
    {% endfor %}

    // Modules
    {%for module in modules if module.home_id == my_home.id  -%}
            Frame {
                Text label="Module {{module.name}}"
                {
                    Default item=netatmo_module_{{module.label}}_id                        label="netatmo2mqtt module {{module.name}} id"                                           
                    Default item=netatmo_module_{{module.label}}_type                      label="netatmo2mqtt module {{module.name}} type"                                         
                    Default item=netatmo_module_{{module.label}}_name                      label="netatmo2mqtt module {{module.name}} name"            
                    Default item=netatmo_module_{{module.label}}_setup_date                label="netatmo2mqtt module {{module.name}} setup_date"                                   
                    Default item=netatmo_module_{{module.label}}_home_id                   label="netatmo2mqtt module {{module.name}} home_id"                                      
                    {% if module.type == "NAPlug" %}
                    //Default item=netatmo_module_{{module.label}}_setup_date                label="netatmo2mqtt module {{module.name}} setup_date"                                        
                    Default item=netatmo_module_{{module.label}}_wifi_strength             label="netatmo2mqtt module {{module.name}} wifi_strength"                                
                    {% endif %}
                    {% if module.type == "NATherm1" %}
                    Default item=netatmo_module_{{module.label}}_boiler_valve_comfort_boost label="netatmo2mqtt module {{module.name}} boiler_valve_comfort_boost"                  
                    {% endif %}
                    {% if module.type != "NAPlug" %}
                    Default item=netatmo_module_{{module.label}}_bridge                    label="netatmo2mqtt module {{module.name}} bridge"                                       
                    Default item=netatmo_module_{{module.label}}_battery_state             label="netatmo2mqtt module {{module.name}} battery_state"                      
                    Default item=netatmo_module_{{module.label}}_battery_level             label="netatmo2mqtt module {{module.name}} battery_level"    
                    Default item=netatmo_module_{{module.label}}_firmware_revision         label="netatmo2mqtt module {{module.name}} firmware_revision"                            
                    Default item=netatmo_module_{{module.label}}_rf_strength               label="netatmo2mqtt module {{module.name}} rf_strength"     
                    Default item=netatmo_module_{{module.label}}_reachable                 label="netatmo2mqtt module {{module.name}} reachable"                                    
                    Default item=netatmo_module_{{module.label}}_boiler_status             label="netatmo2mqtt module {{module.name}} boiler_status"   
                    Default item=netatmo_module_{{module.label}}_room_id                   label="netatmo2mqtt module {{module.name}} room_id"       
                }                               
            }
            {% endif %}
    }
    {% endfor %}
    {% endfor %}
        """
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
