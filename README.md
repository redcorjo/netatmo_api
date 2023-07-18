# Python module for Netatmo

Project repo: https://github.com/redcorjo/netatmo_api.git

## Installation steps (as linux user pi)

```shell
cd ~
git clone https://github.com/redcorjo/netatmo_api.git
cd netatmo_api
echo "Create settings file"
vi src/netatmo.ini
(cd src/service ; ./installer.sh)
```

## Create netatmo openhab files

Let's assume we expect creating all three files 

1. /etc/openhab/things/netatmo.things
2. /etc/openhab/items/netatmo.items
3. /etc/openhab/sitemaps/netatmo.sitemap

```shell
sudo ./netatmo.py  -oh /etc/openhab
```

## Settings file

```
[credentials]
client_id = client_id_value
client_secret = client_secret_value
username = username_value
password = password_value
refresh_token = refresh_token_value
scopes = read_station read_thermostat write_thermostat read_camera write_camera access_camera read_presence access_presence read_smokedetector read_homecoach

[home]
home_id = home_value

[mqtt]
topic =  topic_value
broker = broker_value 
port  = port_value

[global]
frequency = frequency_value

[logging]
severity = INFO
filename = netatmo.log

[http]
host = 0.0.0.0
port = 8000
```

## Adjust truetemperature by external mqtt

Let's say we got configured mqtt base topic as "netatmo2mqtt" and also that our room_id to adjust true temperature is "1234567890" and we want to sync to external measured temperature with value 21.  If we publish a mqtt message with the new temperature, it will be sync with netatmo therm_measured_temperature value. 

This source can be generated from openhab, node-red, or any other home automation source

```shell
mosquitto_pub -t "netatmo2mqtt/1234567890/truetemperature/command" -m 21
```

## Official documentation from Netatmo

<https://dev.netatmo.com/apidocumentation/oauth>
<https://dev.netatmo.com/apidocumentation/energy>


Version: 2023071800
