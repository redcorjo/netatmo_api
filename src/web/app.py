from typing import Optional
from fastapi import FastAPI
from starlette.responses import RedirectResponse
from enum import Enum
import uvicorn
import logging
import os

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

# Netatmo documentaion https://dev.netatmo.com/apidocumentation/energy 

fastapi_parameters = {
    "title": "mqtt_netatmo",
    "description": "Broker APIs to interact with native Netatmo APIs and mqtt endpoints",
    "version": "0.2.0",
    "contact": {
        "name": "Jordi Redondo",
        "email": "jordipromotions@gmail.com",
        "url": "https://github.com/redcorjo/netatmo_api"
    },
    "license_info": {
        "name": "GNU GPLv3",
        "url": "https://raw.githubusercontent.com/redcorjo/netatmo_api/master/LICENSE.md"
    }
}

app = FastAPI(**fastapi_parameters)

class SetThermMode(str, Enum):
    schedule = "schedule"
    away = "away"
    hg = "hg"

class MqttMode(str, Enum):
    inbound = "inbound"
    outbound = "outbound"
    both = "both"

@app.put("/setthermode")
async def put_seththermode(mode: SetThermMode):
    settherm_mode = mode.value
    app_config = app.state.config
    netatmo = app_config["instance"]
    config = app_config["config"]
    response = netatmo.setthermmode(mode=settherm_mode)
    return response

@app.put("/truetemperature/{room_id}")
async def put_truetemperature(room_id: str, corrected_temperature: float):
    app_config = app.state.config
    netatmo = app_config["instance"]
    config = app_config["config"]
    response = netatmo.truetemperature(room_id, corrected_temperature)
    return response

@app.get("/mqtt")
async def get_mqtt(mode: Optional[MqttMode] = MqttMode.both): 
    app_config = app.state.config
    netatmo = app_config["instance"]
    config = app_config["config"]
    if mode == MqttMode.outbound:
        payload = {
        "mqtt_receive_queue": [],
        "mqtt_send_queue": netatmo.mqtt_sent_queue
        }
    elif mode == MqttMode.inbound:
        payload = {
        "mqtt_receive_queue": netatmo.mqtt_receive_queue,
        "mqtt_send_queue": []
        }
    else:
        payload = {
        "mqtt_receive_queue": netatmo.mqtt_receive_queue,
        "mqtt_send_queue": netatmo.mqtt_sent_queue
        }
    return payload

@app.get("/")
async def redirect_docs():
    # return {"Hello": "World"}
    response = RedirectResponse(url='/docs')
    return response

        # logger.info(f"sethermmode = {setthermmode_value}")
        # valid_options = ["schedule", "away"]

def launch_fastapp(port=8000, host="0.0.0.0", settings=None):
    if settings != None:
        app.state.config = settings
    else:
        app.state.config = {}
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    launch_fastapp( host="0.0.0.0", port=8000)