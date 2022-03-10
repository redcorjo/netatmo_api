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
    token = None

    def __init__(self, client_id, client_secret, username, password, home_id, endpoint="https://api.netatmo.com"):
        self.endpoint = endpoint
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
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
