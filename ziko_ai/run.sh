#!/bin/sh
set -eu
umask 077
mkdir -p /data/ziko
chown 1000:1000 /data/ziko
chmod 700 /data/ziko
ZIKO_OPERATOR_USER_ID="$(python -c 'import json; print(json.load(open("/data/options.json")).get("operator_user_id", ""))')"
ZIKO_APPROVED_DEVICE_IDS="$(python -c 'import json; print(json.dumps(json.load(open("/data/options.json")).get("approved_device_ids", [])))')"
export ZIKO_OPERATOR_USER_ID ZIKO_APPROVED_DEVICE_IDS
exec setpriv --reuid=1000 --regid=1000 --init-groups python -m uvicorn ziko.main:app --host 0.0.0.0 --port 8099 --no-proxy-headers --no-access-log
