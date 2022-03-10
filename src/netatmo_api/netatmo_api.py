#!/bin/python3
import requests
import json
import sys
import os
import configparser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Netatmo_API():

    endpoint = "https://api.netatmo.com"
    home_id = None
    token = None
    scopes = "read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach"

    def __init__(self, client_id, client_secret, username, password, home_id: str = None, endpoint: str ="https://api.netatmo.com", scopes: str =None):
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
        payload = json.loads(response.text)
        token = payload["access_token"]
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