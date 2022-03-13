# Python module for Netatmo

Project repo: https://github.com/redcorjo/netatmo_api.git

## Installation steps (as linux user pi)

´´´sh
cd ~
git clone https://github.com/redcorjo/netatmo_api.git
cd netatmo_api
echo "Create settings file"
vi src/netatmo.ini
(cd src/service ; ./installer.sh)
´´´


## Settings file

´´´
[credentials]
client_id = client_id_value
client_secret = client_secret_value
username = username_value
password = password_value
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
´´´

## Official documentation from Netatmo

<https://dev.netatmo.com/apidocumentation/oauth>
<https://dev.netatmo.com/apidocumentation/energy>


Version: 2022031300