#!/bin/bash

create_service()
{
cat <<EOF>/tmp/netatmo.service
[Unit]
Description=Netatmo
After=multi-user.target

[Service]
Type=simple
User=${MYUSER}
WorkingDirectory=${WORKDIR}/
ExecStart=${WORKDIR}/netatmo.sh
Restart=on-abort

[Install]
WantedBy=multi-user.target
EOF
}

echo "Execute as pi user"
MYDIR=$(pwd)
APPDIR=$(dirname $0)
WORKDIR=$(cd ${APPDIR}; cd ../.. ; pwd)
MYUSER=$(whoami)
echo "Create service file"
create_service
sudo mv /tmp/netatmo.service /lib/systemd/system/netatmo.service
echo "Reload daemon"
sudo systemctl daemon-reload
echo "Enable daemon"
sudo systemctl enable netatmo.service
echo "Start daemon"
sudo systemctl start netatmo.service
echo "Check status daemon"
sudo systemctl status netatmo.service
exit