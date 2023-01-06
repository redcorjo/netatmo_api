import logging
import json
import paho.mqtt.client as paho
import os
import time


logging.basicConfig(level=logging.INFO)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod").lower()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler()
logging_formatter = logging.Formatter(
    '%(levelname)-8s [%(filename)s:%(lineno)d] (' + ENVIRONMENT + ') - %(message)s')
stream_handler.setFormatter(logging_formatter)
logger.addHandler(stream_handler)

class MQTT():

    broker = "127.0.0.1"
    port = 1883
    topic = "netatmo"
    client = None

    def __init__(self, broker=None, port=None, topic=None):
        logger.info("Init")
        if broker != None:
            self.broker = broker
        if port != None:
            self.port = int(port)
        if topic != None:
            self.topic = topic
        pass

    def send_message(self, payload, topic=None, item=None):
        if self.client == None:
            self.__connect_queue()
        if topic == None:
            topic = self.topic
        if type(payload) == str:
            message = payload
        else:
            message = json.dumps(payload)
        if item != None:
            topic = f"{topic}/{item}/state"
        else:
            topic = f"{topic}/state"
        self.client.publish(topic, message)
        pass

    def mqtt_on_message(self, client, userdata, message):
        if not message.topic.endswith("/state"):
            epoch = str(time.time())
            logger.info(f"message received {message.payload} - epoch={epoch} ")
            logger.info(f"message topic={message.topic}")
            logger.info(f"message qos={message.qos}")
            logger.info(f"message retain flag={message.retain}")

    def subscribe_topic(self, topic=None, qos=1, on_message=None):
        if self.client == None:
            self.__connect_queue()
        if topic == None:
            topic = f"{self.topic}/+/update" 
        logger.info(f"Subscribing to mqtt topic {topic}")
        self.client.subscribe(topic, qos=qos)
        if on_message == None:
            self.client.on_message=self.mqtt_on_message
        else:
            self.client.on_message=on_message
        self.client.loop_forever()

    def __connect_queue(self):
        paho_client = "mqtt_netatmo_" + str(time.time())
        client = paho.Client(paho_client)
        client.connect(self.broker, self.port)
        self.client = client
        