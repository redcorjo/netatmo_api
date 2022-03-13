#!/bin/bash

cp netatmo.service /lib/systemd/system/netatmo.service
test -d /home/pi/netatmo || mkdir /home/pi/netatmo
cp -R ../src /home/pi/netatmo
chmod 755 /home/pi/netatmo/src/netatmpo.py
systemctl daemon-reload
systemctl enable netatmo.service
systemctl start netatmo.service