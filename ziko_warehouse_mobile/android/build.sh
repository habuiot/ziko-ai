#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
SDK="$(printenv ANDROID_SDK_ROOT || true)"
if [ -z "$SDK" ]; then SDK="/mnt/pve/ziko-data/ziko-buildtools/android"; fi
JAVA_HOME="$(printenv JAVA_HOME || true)"
if [ -z "$JAVA_HOME" ]; then JAVA_HOME="/mnt/pve/ziko-data/ziko-buildtools/jvm/usr/lib/jvm/java-21-openjdk-amd64"; fi
TOOLS="$SDK/build-tools/36.0.0"
JAR="$SDK/platforms/android-35/android.jar"
WORK="$ROOT/build"
mkdir -p "$WORK/classes" "$WORK/generated" "$WORK/dex" "$ROOT/out"
export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"
test -f "$JAR"
test -x "$TOOLS/aapt2"
test -x "$JAVA_HOME/bin/javac"
"$TOOLS/aapt2" compile --dir "$ROOT/res" -o "$WORK/resources.zip"
"$TOOLS/aapt2" link -o "$WORK/resources.apk" -I "$JAR" \
    --manifest "$ROOT/AndroidManifest.xml" --java "$WORK/generated" \
    --min-sdk-version 29 --target-sdk-version 35 --auto-add-overlay \
    --version-code 170000 --version-name "1.7.0" \
    -R "$WORK/resources.zip"
"$JAVA_HOME/bin/javac" -source 17 -target 17 -encoding UTF-8 -cp "$JAR" \
    -d "$WORK/classes" "$ROOT/src/hu/ziko/warehouse/MainActivity.java" \
    "$WORK/generated/hu/ziko/warehouse/R.java"
"$TOOLS/d8" --min-api 29 --lib "$JAR" --output "$WORK/dex" $(find "$WORK/classes" -name '*.class')
python3 - "$WORK/resources.apk" "$WORK/dex/classes.dex" "$WORK/unsigned.apk" <<'PY'
from pathlib import Path
from zipfile import ZipFile
import shutil,sys
base,classes,dest=map(Path,sys.argv[1:])
shutil.copyfile(base,dest)
with ZipFile(dest,'a') as zipfile:zipfile.write(classes,'classes.dex')
print("APK_RESOURCES_AND_DEX_JOINED",dest.stat().st_size)
PY
"$TOOLS/zipalign" -f 4 "$WORK/unsigned.apk" "$WORK/aligned.apk"
KEYSTORE="$(printenv ZIKO_MOBILE_KEYSTORE || true)"
KEY_PASS_FILE="$(printenv ZIKO_MOBILE_KEY_PASS_FILE || true)"
# Reuse a private, persistent ZIKO signing identity for repeatable app upgrades.
# Never print or copy these files into a release package.
if [ -z "$KEYSTORE" ] && [ -f "/mnt/pve/ziko-data/ziko-buildtools/private-signing/warehouse-mobile-release.p12" ]; then
  KEYSTORE="/mnt/pve/ziko-data/ziko-buildtools/private-signing/warehouse-mobile-release.p12"
  KEY_PASS_FILE="/mnt/pve/ziko-data/ziko-buildtools/private-signing/warehouse-mobile-password.txt"
fi
KEY_ALIAS="$(printenv ZIKO_MOBILE_KEY_ALIAS || true)"
if [ -z "$KEY_ALIAS" ]; then KEY_ALIAS="ziko-warehouse-mobile"; fi
if [ -n "$KEYSTORE" ] && [ -n "$KEY_PASS_FILE" ]; then
  "$TOOLS/apksigner" sign --ks "$KEYSTORE" \
    --ks-key-alias "$KEY_ALIAS" \
    --ks-pass "file:$KEY_PASS_FILE" \
    --out "$ROOT/out/ZIKO-Warehouse-Android-1.7.0.apk" \
    "$WORK/aligned.apk"
  "$TOOLS/apksigner" verify --verbose --print-certs "$ROOT/out/ZIKO-Warehouse-Android-1.7.0.apk"
  "$TOOLS/aapt" dump badging "$ROOT/out/ZIKO-Warehouse-Android-1.7.0.apk" | head -9
else
  cp "$WORK/aligned.apk" "$ROOT/out/ZIKO-Warehouse-Android-1.7.0-UNSIGNED.apk"
  echo "No release signing key configured. Package is UNSIGNED (source build only)."
fi

