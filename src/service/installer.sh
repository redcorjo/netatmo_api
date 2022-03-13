#!/bin/bash

echo "Execute as pi user"

sudo cp netatmo.service /lib/systemd/system/netatmo.service
test -d /home/pi/netatmo || mkdir /home/pi/netatmo
cp -R ../src /home/pi/netatmo
chmod 755 /home/pi/netatmo/src/netatmpo.py
sudo systemctl daemon-reload
sudo systemctl enable netatmo.service
sudo systemctl start netatmo.service