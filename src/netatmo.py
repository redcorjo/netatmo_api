#!/bin/python3
import requests
import json
import sys
import os
import configparser
import logging
from optparse import OptionParser
from netatmo_api.netatmo_api import Netatmo_API

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_settings():
    parser = OptionParser()
    parser.add_option("-f", "--configfile", dest="filename",
                      help="init config file", metavar="FILE")
    parser.add_option("-s", "--sechedule", dest="filename",
                      help="schedule", metavar="FILE")

    settings = parser.parse_args()
    return settings


def main():
    settings_file = sys.argv[0].replace(".py", ".ini")

    settings = get_settings()

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
        config["mqtt"]["topic"] = "netatmo/metrics"
        config["mqtt"]["broker"] = "127.0.0.1"
        config["mqtt"]["port"] = "1883"
        with open(settings_file, "w") as config_file:
            config.write(config_file)
        return
    # Credentials
    client_id = config["credentials"]["client_id"]
    client_secret = config["credentials"]["client_secret"]
    username = config["credentials"]["username"]
    password = config["credentials"]["password"]
    try:
        scopes = config["credentials"]["scopes"]
    except:
        scopes = None

    # Settings home section
    home_id = config["home"]["home_id"]

    # Settings mqtt
    topic =  config["mqtt"]["topic"]
    broker = config["mqtt"]["broker"]
    port  = int(config["mqtt"]["port"])

    netatmo = Netatmo_API(client_id, client_secret,
                          username, password, scopes=scopes)
    if len(sys.argv) > 0:
        parameter = sys.argv[1]
    else:
        parameter = "schedule"
    response1 = netatmo.homesdata()
    response2 = netatmo.homestatus()
    response3 = netatmo.setthermmode(mode=parameter)
    return None


if __name__ == "__main__":
    main()
