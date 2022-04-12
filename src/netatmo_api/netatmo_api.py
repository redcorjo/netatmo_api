#!/bin/python3
from urllib import response
import requests
import json
import sys
import os
import configparser
import logging
from lxml import html

# logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s',
#     datefmt='%Y-%m-%d:%H:%M:%S',
#     level=logging.INFO)
logger = logging.getLogger(__name__)
#logger.propagate = False

class Netatmo_API():

    endpoint = "https://api.netatmo.com"
    home_id = None
    token = None
    session = None
    scopes = "read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach"

    def __init__(self, client_id, client_secret, username, password, home_id: str = None, endpoint: str ="https://api.netatmo.com", scopes: str =None):
        logger.info("Init")
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        if home_id != None:
            self.home_id = home_id
        if scopes != None:
            self.scopes = scopes

    def get_default_home_id(self):
        payload = self.homesdata()
        home_id = payload["body"]["homes"][0]["id"]
        return home_id

    def get_token(self):
        # https://dev.netatmo.com/apidocumentation/oauth
        token = None
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        request_body={
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "scope": self.scopes
        }
        response = requests.post(self.endpoint + "/oauth2/token", data=request_body, headers=headers)
        if response.status_code == 200:
            payload = json.loads(response.text)
            token = payload["access_token"]
            self.token = token
        else:
            logger.error(f"Remote api returned error code {{response.status_code}} . {{response.text}} ")
            token = None
        return token

    def homesdata(self, home_id: str = None,  gateways_types: list = None):
        endpoint = f"{self.endpoint}/api/homesdata"
        parameters = {
        }
        if home_id != None:
            parameters["home_id"] = home_id
        elif self.home_id != None:
            parameters["home_id"] = self.home_id
        if gateways_types != None:
            parameters["gateways_types"] = gateways_types
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.get(endpoint, params=parameters, headers=headers)
        if response.status_code == 200:
            payload = json.loads(response.content)
        else:
            payload = {"status": "failed"}
        return payload

    def homestatus(self, home_id: str = None,  device_types: list = None):
        endpoint = f"{self.endpoint}/api/homestatus"
        parameters = {
        }
        if home_id != None:
            parameters["home_id"] = home_id
        elif self.home_id != None:
            parameters["home_id"] = self.home_id
        else:
            parameters["home_id"] = self.get_default_home_id()
        if device_types != None:
            parameters["device_types"] = device_types
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.get(endpoint, params=parameters, headers=headers)
        if response.status_code == 200:
            payload = json.loads(response.content)
        else:
            payload = {"status": "failed"}
        return payload

    # # TODO: Pending
    # def getroommeasure(self):
    #     endpoint = f"{self.endpoint}/api/getroommeasure"
    #     parameters = {
    #     }
    #     if self.token == None:
    #         self.get_token()
    #     headers = {
    #         "accept": "application/json",
    #         "Authorization": "Bearer " + self.token
    #     }
    #     response = requests.get(endpoint, params=parameters, headers=headers)
    #     if response.status_code == 200:
    #         payload = json.loads(response.content)
    #     else:
    #         payload = {"status": "failed"}
    #     return payload

    # # TODO: Pending
    # def setroomthermpoint(self, mode="away"):
    #     endpoint = f"{self.endpoint}/api/setroomthermpoint"
    #     parameters = {
    #         "home_id": self.home_id,
    #         "mode": mode
    #     }
    #     if self.token == None:
    #         self.get_token()
    #     headers = {
    #         "accept": "application/json",
    #         "Authorization": "Bearer " + self.token
    #     }
    #     response = requests.post(endpoint, params=parameters, headers=headers)
    #     if response.status_code == 200:
    #         payload = json.loads(response.content)
    #     else:
    #         payload = {"status": "failed"}
    #     return payload

    def setthermmode(self, home_id: str = None,  mode="away"):
        endpoint = f"{self.endpoint}/api/setthermmode"
        parameters = {}
        if home_id != None:
            parameters["home_id"] = home_id
        elif self.home_id != None:
            parameters["home_id"] = self.home_id
        else:
            parameters["home_id"] = self.get_default_home_id()
        parameters["mode"] = mode
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.post(endpoint, params=parameters, headers=headers)
        if response.status_code == 200:
            payload = json.loads(response.content)
        else:
            payload = {"status": "failed"}
        current_status = self.homestatus(home_id=parameters["home_id"])
        return current_status

    def get_xsrf_token(self):
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.get("https://auth.netatmo.com/de-DE/access/login", headers=headers)
        all_cookies = response.cookies.get_dict()
        if "XSRF-TOKEN" in all_cookies:
            XSRF_TOKEN = all_cookies["XSRF-TOKEN"]
        else:
            XSRF_TOKEN = ""
        return XSRF_TOKEN

    def login_page(self, username=None, password=None):
        if username == None:
            username = self.username
        if password == None:
            password = self.password
        if self.session == None:
            self.session = requests.Session()
        req = self.session.get("https://auth.netatmo.com/en-us/access/login")
        if req.status_code != 200:
            logger.error("Unable to contact https://auth.netatmo.com/en-us/access/login")
            logger.critical("Error: {0}".format(req.status_code))
            sys.exit(-1)
        else:
            logger.info("Successfully got session cookie from https://auth.netatmo.com/en-us/access/login")

        """
        check if we got a valid session cookie
        """
        loginpage = html.fromstring(req.text)
        token = loginpage.xpath('//input[@name="_token"]/@value')

        if token is None:
            logger.critical("No _token value found in response from https://auth.netatmo.com/en-us/access/login")
            sys.exit(-1)
        else:
            logger.info("Found _token value {0} in response from https://auth.netatmo.com/en-us/access/login".format(token))

        """
        build the payload for authentication
        """
        payload = {'email': username,
                    'password': password,
                    '_token': token } 

        param = { 'next_url' : 'https://my.netatmo.com/app/energy' }

        """
        login and grab an access token
        """
        req2 = self.session.post("https://auth.netatmo.com/access/postlogin", params=param, data=payload)

        cookies = req2.cookies

        session_cookies = self.session.cookies.get_dict()
        if "netatmocomaccess_token" in session_cookies:
            access_token = session_cookies["netatmocomaccess_token"].replace("%7C","|")
            authentication_value = f"Bearer {access_token}"
        else:
            raise Exception("Error with access token")

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": authentication_value
        }
        return headers

    def set_truetemperature(self, room_id, corrected_temperature, username=None, password=None, home_id=None):
        if username == None:
            username = self.username
        if password == None:
            password = self.password
        if home_id == None:
            home_id = self.get_default_home_id()

        session = requests.Session()

        headers = self.login_page()

        payload={"home_id": home_id}
        req3 = session.get(f"{self.endpoint}/api/homestatus", headers=headers, params=payload)

        home_data = json.loads(req3.text)
        home = home_data["body"]["home"]
        rooms = home["rooms"]
        current_temperature = corrected_temperature
        for room in rooms:
            if room["id"] == room_id:
                current_temperature = room["therm_measured_temperature"]
                break
        # netatmocomaccess_token
        payload={"home_id": home_id,"room_id": room_id,"current_temperature":current_temperature,"corrected_temperature":corrected_temperature}
        #req4 = session.post("https://app.netatmo.net/api/truetemperature",  json=payload, headers=headers)
        req4 = session.post(f"{self.endpoint}/api/truetemperature",  json=payload, headers=headers)
        payload_response = json.loads(req4.text)
        logger.info(f"Done status={req4.status_code} payload={payload_response}")
        return payload_response

    # # TODO: Pending
    # def getmeasure(self):
    #     endpoint = f"{self.endpoint}/api/getmmeasure"
    #     parameters = {
    #     }
    #     if self.token == None:
    #         self.get_token()
    #     headers = {
    #         "accept": "application/json",
    #         "Authorization": "Bearer " + self.token
    #     }
    #     response = requests.get(endpoint, params=parameters, headers=headers)
    #     if response.status_code == 200:
    #         payload = json.loads(response.content)
    #     else:
    #         payload = {"status": "failed"}
    #     return payload

    # # TODO: Pending
    # def synchomeschedule(self, mode="away"):
    #     endpoint = f"{self.endpoint}/api/synchomeschedule"
    #     parameters = {
    #         "home_id": self.home_id,
    #         "mode": mode
    #     }
    #     if self.token == None:
    #         self.get_token()
    #     headers = {
    #         "accept": "application/json",
    #         "Authorization": "Bearer " + self.token
    #     }
    #     response = requests.post(endpoint, params=parameters, headers=headers)
    #     if response.status_code == 200:
    #         payload = json.loads(response.content)
    #     else:
    #         payload = {"status": "failed"}
    #     return payload

    def switchhomeschedule(self, schedule_id: str, home_id: str = None):
        endpoint = f"{self.endpoint}/api/switchhomeschedule"
        parameters = {}
        if home_id != None:
            parameters["home_id"] = home_id
        elif self.home_id != None:
            parameters["home_id"] = self.home_id
        else:
            parameters["home_id"] = self.get_default_home_id()
        parameters["schedule_id"] = schedule_id
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.post(endpoint, params=parameters, headers=headers)
        if response.status_code == 200:
            payload = json.loads(response.content)
        else:
            payload = {"status": "failed"}
        return payload

