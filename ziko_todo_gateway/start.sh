#!/bin/sh
set -eu
umask 077
# Setup only this app's dedicated persistent data volume.
install -d -m 0700 -o zikotodo -g zikotodo /data
exec su-exec zikotodo:zikotodo python /opt/zikotodo/server.py
