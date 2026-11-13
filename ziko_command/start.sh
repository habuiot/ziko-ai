#!/bin/sh
set -eu
umask 077
install -d -m 0700 -o zikocommand -g zikocommand /data
exec su-exec zikocommand:zikocommand python /opt/ziko-command/server.py
