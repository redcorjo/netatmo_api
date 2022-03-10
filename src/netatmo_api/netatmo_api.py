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

    def __init__(self, client_id, client_secret, username, password, home_id: str = None, endpoint: str ="https://api.netatmo.com"):
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        if home_id != None:
            self.home_id = home_id

    def get_token(self):
        token = None
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        request_body={
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": self.username,
            "password": self.password,
            "scope": "write_thermostat"
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
        return response

    def homestatus(self, home_id: str,  device_types: list = None):
        endpoint = f"{self.endpoint}/api/homestatus"
        parameters = {
        }
        if home_id != None:
            parameters["home_id"] = home_id
        else:
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
        return response

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
    #     return response

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
    #     return response

    def setthermmode(self, mode="away"):
        endpoint = f"{self.endpoint}/api/setthermmode"
        parameters = {
            "home_id": self.home_id,
            "mode": mode
        }
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.post(endpoint, params=parameters, headers=headers)
        return response

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
    #     return response

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
    #     return response

    def switchhomeschedule(self, schedule_id: str, home_id: str = None):
        endpoint = f"{self.endpoint}/api/switchhomeschedule"
        if home_id != None:
            my_home_id = home_id
        else:
            my_home_id = self.home_id
        parameters = {
            "home_id": self.my_home_id,
            "schedule_id": schedule_id
        }
        if self.token == None:
            self.get_token()
        headers = {
            "accept": "application/json",
            "Authorization": "Bearer " + self.token
        }
        response = requests.post(endpoint, params=parameters, headers=headers)
        return response