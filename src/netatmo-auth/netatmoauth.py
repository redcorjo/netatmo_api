#!/bin/python3
import requests
import json
import os
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

class NetatmoAuth():

    endpoint = "https://api.netatmo.com"
    cookies_file = os.path.realpath(os.path.dirname(__file__)) + "/tmp/cookies.tmp"
    token = None
    access_token = None
    session = None
    redirect_uri = None
    scopes = "read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach"

    def __init__(self, client_id, client_secret, username, password, endpoint: str ="https://api.netatmo.com", scopes: str =None, access_token: str = None, redirect_uri: str =None, refresh_token: str = None):
        logger.info("Init")
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.refresh_token = refresh_token
        self.username = username
        self.password = password
        if scopes != None:
            self.scopes = scopes
        if access_token != None:
            self.access_token = access_token

    def get_token(self):
        login_headers = self.get_session_headers()
        # https://dev.netatmo.com/apidocumentation/oauth
        token = login_headers["Authorization"].split(" ")[1]
        self.token = token
        return token


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
                    #"website": "",
                    '_token': token } 

            param = { 'next_url' : 'https://my.netatmo.com/app/energy' }
            req3 = self.session.post("https://auth.netatmo.com/access/postlogin", params=param, data=payload, headers=headers)
            headers = self.get_access_token_from_cookie(self.session.cookies)
            req4 = self.session.get("https://app.netatmo.net/api/homesdata", headers=headers)
            if req4.status_code == 200:
                logger.info("Successfully obtained credentials")
            else:
                logger.error("Error obtaining credentials")
                raise Exception("Error obtaining credentials")
            my_session_cookies = self.session.cookies
            temp_dir = os.path.realpath(os.path.dirname(self.cookies_file)) 
            if not os.path.exists(temp_dir):
                logger.info(f"Creating {temp_dir}")
                os.makedirs(temp_dir)
            #my_session_serialized_cookies = pickle.dumps(my_session_cookies)
            with open(self.cookies_file, "wb") as my_file:
                pickle.dump(my_session_cookies, my_file)
                logger.info(f"Persisted session cookies at {self.cookies_file}")
                successful = True
        #loginpage = html.fromstring(req.text)
        #token = loginpage.xpath('//input[@name="_token"]/@value')

        if successful == False:
            logger.critical("No _token value found in response from https://auth.netatmo.com/en-us/access/login")
            raise Exception("No _token value found in response from https://auth.netatmo.com/en-us/access/login")
            #sys.exit(-1)
        else:
            logger.debug("Found _token value {0} in response from https://auth.netatmo.com/en-us/access/login".format(token))
        return headers
        
    def get_access_token_from_cookie(self, cookies):
        session_cookies = cookies.get_dict()
        if "netatmocomaccess_token" in session_cookies:
            access_token = session_cookies["netatmocomaccess_token"].replace("%7C","|")
            authentication_value = f"Bearer {access_token}"
        else:
            raise Exception("Error with access token")
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

