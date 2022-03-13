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
create_service
sudo mv /tmp/netatmo.service /lib/systemd/system/netatmo.service
sudo systemctl daemon-reload
sudo systemctl enable netatmo.service
sudo systemctl start netatmo.service
exit