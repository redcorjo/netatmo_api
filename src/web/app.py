from typing import Optional
from fastapi import FastAPI
from enum import Enum
import uvicorn
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = FastAPI()

class SetThermMode(str, Enum):
    schedule = "schedule"
    away = "away"

@app.put("/setthermode")
async def put_seththermode(mode: SetThermMode):
    settherm_mode = mode.value
    app_config = app.state.config
    netatmo = app_config["instance"]
    config = app_config["config"]
    response = netatmo.setthermmode(mode=settherm_mode)
    return response


@app.get("/")
async def read_root():
    return {"Hello": "World"}

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