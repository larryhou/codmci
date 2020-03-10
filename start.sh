#!/usr/bin/env bash

cd $(dirname $0)

set -x

PLIST_PATH=$1
if [ -z "${PLIST_PATH}" ] || [ ! -f "${PLIST_PATH}" ]
then
    exit 1
fi

SCRIPT_INSTALL_PATH=~/.codmci
DAEMON_INSTALL_PATH=~/Library/LaunchAgents
DAEMON_IDENTIFIER=$(grep -A 1 Label $PLIST_PATH | tail -n 1 | awk -F'>' '{print $2}' | awk -F'<' '{print $1}')
CONFIG_INSTALL_PATH=${DAEMON_INSTALL_PATH}/${DAEMON_IDENTIFIER}.plist

rsync -av --exclude='/.*' --exclude='/__*' ./ ${SCRIPT_INSTALL_PATH}
cp -fv plist/${DAEMON_IDENTIFIER}.plist ${CONFIG_INSTALL_PATH}
sed -i '' "s/~/\/Users\/$(whoami)/g" ${CONFIG_INSTALL_PATH}

cat ${CONFIG_INSTALL_PATH} | grep log \
| awk -F'>' '{print $2}' \
| awk -F'<' '{print $1}' | xargs -I{} dirname {} \
| xargs -I{} mkdir -pv {}

launchctl stop ${DAEMON_IDENTIFIER}
launchctl unload ${CONFIG_INSTALL_PATH}
launchctl load -w -F ${CONFIG_INSTALL_PATH}