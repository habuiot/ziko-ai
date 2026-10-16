#!/bin/sh
set -eu
archive=${1:?Add meg a /config/Ziko_HA_Tools_0.2.0.zip elérési útját}
test -f "$archive" || { echo 'A ZIP nem található.'; exit 1; }
command -v ha >/dev/null 2>&1 || { echo 'Ezt a Home Assistant Terminal & SSH alkalmazásában futtasd.'; exit 1; }
if ! command -v python3 >/dev/null 2>&1; then
  command -v apk >/dev/null 2>&1 || { echo 'Python 3 szükséges. Használd a Studio Code Server terminálját vagy a kézi/HACS telepítést.'; exit 1; }
  echo 'Python telepítése a terminál alkalmazásba…'
  apk add --no-cache python3
fi
stage=$(mktemp -d /tmp/ziko-setup.XXXXXX)
trap 'rm -rf "$stage"' EXIT
unzip -p "$archive" install_ziko.py > "$stage/install_ziko.py"
python3 "$stage/install_ziko.py" "$archive"
python3 "$stage/install_ziko.py" "$archive" --apply --restart
