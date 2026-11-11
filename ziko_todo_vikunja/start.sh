#!/bin/sh
set -eu
umask 077

# Only this add-on's isolated /data volume is writable.
mkdir -p /data/db /data/files
chown -R vikunja:vikunja /data/db /data/files
chmod 0700 /data/db /data/files

# Stable signing key (not printed and never committed to GitHub).
if [ ! -s /data/service-secret ]; then
  head -c 48 /dev/urandom | base64 | tr -d '\n' > /data/service-secret
  printf '\n' >> /data/service-secret
fi
chmod 0600 /data/service-secret
export VIKUNJA_SERVICE_SECRET="$(cat /data/service-secret)"

OPTIONS=/data/options.json
if [ -f "$OPTIONS" ]; then
  export VIKUNJA_SERVICE_PUBLICURL="$(jq -r '.public_url // "http://homeassistant.local:3456/"' "$OPTIONS")"
  export VIKUNJA_SERVICE_ENABLEREGISTRATION="$(jq -r '.enable_registration // true' "$OPTIONS")"
  export VIKUNJA_SERVICE_TIMEZONE="$(jq -r '.timezone // "Europe/Budapest"' "$OPTIONS")"
  export VIKUNJA_LOG_LEVEL="$(jq -r '.log_level // "info"' "$OPTIONS")"
else
  export VIKUNJA_SERVICE_PUBLICURL="http://homeassistant.local:3456/"
  export VIKUNJA_SERVICE_ENABLEREGISTRATION="true"
  export VIKUNJA_SERVICE_TIMEZONE="Europe/Budapest"
  export VIKUNJA_LOG_LEVEL="info"
fi

export VIKUNJA_SERVICE_INTERFACE=":3456"
export VIKUNJA_DATABASE_TYPE="sqlite"
export VIKUNJA_DATABASE_PATH="/data/db/vikunja.db"
export VIKUNJA_FILES_BASEPATH="/data/files"
export VIKUNJA_CORS_ENABLE="false"

echo "Starting Vikunja 2.8.0; isolated data directory, TZ=$VIKUNJA_SERVICE_TIMEZONE"
# The first local account must be created interactively; disable open
# registration immediately afterwards, before adding further users.
exec su-exec vikunja:vikunja /usr/local/bin/vikunja
