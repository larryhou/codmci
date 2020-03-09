#!/usr/bin/env bash

cd $(dirname $0)

set -x

SCRIPT_INSTALL_PATH=/opt/codmci
DAEMON_INSTALL_PATH=/Library/LaunchDaemons
DAEMON_IDENTIFIER=com.codmci.slave

sudo mkdir -pv ${SCRIPT_INSTALL_PATH}
sudo cp -fv *.py ${SCRIPT_INSTALL_PATH}
ls -l ${SCRIPT_INSTALL_PATH}

sudo cp -fv plist/${DAEMON_IDENTIFIER}.plist ${DAEMON_INSTALL_PATH}
sudo chown root:wheel ${DAEMON_INSTALL_PATH}/${DAEMON_IDENTIFIER}.plist

cat plist/${DAEMON_IDENTIFIER}.plist | grep log \
| awk -F'>' '{print $2}' \
| awk -F'<' '{print $1}' | xargs -I{} dirname {} \
| xargs -I{} sudo mkdir -pv {}

sudo launchctl stop ${DAEMON_IDENTIFIER}
sudo launchctl unload ${DAEMON_INSTALL_PATH}/${DAEMON_IDENTIFIER}.plist
sudo launchctl load -w -F ${DAEMON_INSTALL_PATH}/${DAEMON_IDENTIFIER}.plist