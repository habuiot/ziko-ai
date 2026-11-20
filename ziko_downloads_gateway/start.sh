#!/bin/sh
# Supervisor supplies root-only options; drop to unprivileged zdl before serving.
set -eu
umask 077
test -r /data/options.json
cp /data/options.json /tmp/zdl-options.json
chown zdl:zdl /tmp/zdl-options.json
chmod 0600 /tmp/zdl-options.json
exec su-exec zdl python3 -B /opt/zdl-ingress/gateway.py
