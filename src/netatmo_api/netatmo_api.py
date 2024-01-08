#!/bin/python3
from urllib import response
import requests
import json
import sys
import os
import configparser
import logging
from lxml import html
import pickle

logging.basicConfig(level=logging.INFO)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod").lower()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
logging_formatter = logging.Formatter(
    '%(levelname)-8s [%(filename)s:%(lineno)d] (' + ENVIRONMENT + ') - %(message)s')
stream_handler.setFormatter(logging_formatter)
logger.addHandler(stream_handler)
logger.propagate = False

class Netatmo_API():

    endpoint = "https://api.netatmo.com"
    cookies_file = os.path.realpath(os.path.dirname(__file__)) + "/tmp/cookies.tmp"
    home_id = None
    token = None
    access_token = None
    session = None
    redirect_uri = None
    scopes = "read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach"

    def __init__(self, client_id, client_secret, username, password, home_id: str = None, endpoint: str ="https://api.netatmo.com", scopes: str =None, access_token: str = None, redirect_uri: str =None, refresh_token: str = None):
        logger.info("Init")
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.refresh_token = refresh_token
        self.username = username
        self.password = password
        if home_id != None:
            self.home_id = home_id
        if scopes != None:
            self.scopes = scopes
        if access_token != None:
            self.access_token = access_token

    def get_default_home_id(self):
        payload = self.homesdata()
        home_id = payload["body"]["homes"][0]["id"]
        return home_id

    def get_token(self):
        login_headers = self.get_session_headers()
        # https://dev.netatmo.com/apidocumentation/oauth
        token = login_headers["Authorization"].split(" ")[1]
        self.token = token
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
        if self.token == None:
            logger.warning("Error. Not possible to get session token")
            return None
        headers = {
            "User-Agent": "netatmo-home",
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
            "User-Agent": "netatmo-home",
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
            "User-Agent": "netatmo-home",
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
            "User-Agent": "netatmo-home",
            "accept": "application/json",
            "Authorization": "Bearer " + self.access_token
        }
        response = requests.get("https://auth.netatmo.com/de-DE/access/login", headers=headers)
        all_cookies = response.cookies.get_dict()
        if "XSRF-TOKEN" in all_cookies:
            XSRF_TOKEN = all_cookies["XSRF-TOKEN"]
        else:
            XSRF_TOKEN = ""
        return XSRF_TOKEN

    def get_session_headers(self, username=None, password=None):
        if username == None:
            username = self.username
        if password == None:
            password = self.password
        headers = {
            "User-Agent": "netatmo-home"
            }
        successful = False   
        if self.session == None:
            session = requests.Session()
            self.session = session
        else:
            session = self.session
        if os.path.exists(self.cookies_file):
            with open(self.cookies_file, "rb") as my_file:
                my_session_cookies = pickle.load(my_file)
            self.session.cookies = my_session_cookies
            """
            check if we got a valid session cookie
            """
            req1 = self.session.get("https://auth.netatmo.com/access/csrf")
            if req1.status_code == 200:
                token_data = json.loads(req1.text)
                token = token_data["token"]
                try:
                    headers = self.get_access_token_from_cookie(self.session.cookies)
                except Exception as e:
                    logger.warning("Error " + str(e))
                    logger.info(f"Removing {self.cookies_file}")
                    os.remove(self.cookies_file)
                if os.path.exists(self.cookies_file):
                    req2 = self.session.get("https://app.netatmo.net/api/homesdata", headers=headers)
                    if req2.status_code == 200:
                        logger.info("Obtained credentials from cache")
                        successful = True
                    else:
                        logger.info(f"Removing {self.cookies_file}")
                        os.remove(self.cookies_file)
            else:
                logger.info(f"Removing {self.cookies_file}")
                os.remove(self.cookies_file)
        if successful == False:
            logger.info("Required to re-authenticate to obtain new credentials")
            req = self.session.get("https://auth.netatmo.com/en-us/access/login", headers=headers)
            if req.status_code != 200:
                logger.error("Unable to contact https://auth.netatmo.com/en-us/access/login")
                logger.critical("Error: {0}".format(req.status_code))
                raise Exception("Error: {0}".format(req.status_code))
                #sys.exit(-1)
            else:
                logger.info("Successfully got session cookie from https://auth.netatmo.com/en-us/access/login")
            self.session.cookies.set("netatmocomlast_app_used", "app_thermostat", domain=".netatmo.com")
            req2 = self.session.get("https://auth.netatmo.com/access/csrf")
            if req2.status_code == 200:
                token_data = json.loads(req2.text)
                token = token_data["token"]
            else:
                logger.warning("Problem obtaining session token")
                raise Exception("Problem obtaining session token")
                # sys.exit(-1)
            payload = {'email': username,
                    'password': password,
                    "stay_logged": "on",
                    #"website": None,
                    '_token': token } 

            req3 = self.session.post("https://auth.netatmo.com/access/postlogin", data=payload, headers=headers, allow_redirects=False)
            cookies = self.session.cookies.get_dict()
            param = { 'next_url' : 'https://my.netatmo.com' }
            req4 = self.session.get("https://auth.netatmo.com/access/keychain", params=param, headers=headers, allow_redirects=False)
            cookies = self.session.cookies.get_dict()
            headers = self.get_access_token_from_cookie(self.session.cookies)
            req5 = self.session.get("https://app.netatmo.net/api/homesdata", headers=headers)
            if req5.status_code == 200:
                logger.info("Successfully obtained credentials")
            else:
                logger.error("Error obtaining credentials")
                raise Exception("Error obtaining credentials")
            my_session_cookies = self.session.cookies
            temp_dir = os.path.realpath(os.path.dirname(self.cookies_file)) 
            if not os.path.exists(temp_dir):
                logger.info(f"Creating {temp_dir}")
                os.makedirs(temp_dir)
            with open(self.cookies_file, "wb") as my_file:
                pickle.dump(my_session_cookies, my_file)
                logger.info(f"Persisted session cookies at {self.cookies_file}")
                successful = True
        if successful == False:
            logger.critical("No _token value found in response from https://auth.netatmo.com/en-us/access/login")
            raise Exception("No _token value found in response from https://auth.netatmo.com/en-us/access/login")
        else:
            logger.debug("Found _token value {0} in response from https://auth.netatmo.com/en-us/access/login".format(token))
        return headers
        
    def get_access_token_from_cookie(self, cookies):
        session_cookies = cookies.get_dict()
        cookie_name = "netatmocomaccess_token"
        if cookie_name in session_cookies:
            access_token = session_cookies[cookie_name].replace("%7C","|")
            authentication_value = f"Bearer {access_token}"
        else:
            raise Exception(f"Error with access token {cookie_name}")
        headers = {
            "User-Agent": "netatmo-home",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": authentication_value
        }
        return headers
            
    def login_page(self, username=None, password=None):
        if username == None:
            username = self.username
        if password == None:
            password = self.password
        if self.session == None:
            self.session = requests.Session()

        headers = {
            "User-Agent": "netatmo-home"
            }
             
        headers = self.get_session_headers(username=username, password=password)  
        return headers

    def set_truetemperature(self, room_id, corrected_temperature, username=None, password=None, home_id=None):
        if username == None:
            username = self.username
        if password == None:
            password = self.password
        if home_id == None:
            home_id = self.get_default_home_id()

        if self.session == None:
            session = requests.Session()
            self.session = session
        else:
            session = self.session

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
            "User-Agent": "netatmo-home",
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.post(endpoint, params=parameters, headers=headers)
        if response.status_code == 200:
            payload = json.loads(response.content)
        else:
            payload = {"status": "failed"}
        return payload
