import logging
import json
import paho.mqtt.client as paho


logging.basicConfig(format='%(levelname)-8s [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d:%H:%M:%S',
    level=logging.INFO)
logger = logging.getLogger(__name__)
logger.propagate = False

class MQTT():

    broker = "127.0.0.1"
    port = 1883
    topic = "netatmo"
    client = None

    def __init__(self, broker=None, port=None, topic=None):
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
            topic = f"{topic}/{item}/status"
        else:
            topic = f"{topic}/status"
        self.client.publish(topic, message)
        pass

    def __connect_queue(self):
        client = paho.Client("mqtt_netatmo")
        client.connect(self.broker, self.port)
        self.client = client