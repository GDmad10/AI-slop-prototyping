#!/bin/bash
# Ghost IPA — one-shot Theos build (macOS or Linux builder).
# Usage: ./build.sh [device-ip]
set -euo pipefail
if [ -z "${THEOS:-}" ]; then
  echo "THEOS not set. Install: git clone --recursive https://github.com/theos/theos.git ~/theos"
  echo "Then: export THEOS=~/theos  (plus an iOS SDK in \$THEOS/sdks)"
  exit 1
fi
command -v dpkg-deb >/dev/null || { echo "need dpkg-deb (apt install dpkg)"; exit 1; }
make package FINALPACKAGE=1
DEB=$(ls -t packages/*.deb | head -1)
echo "BUILT: $DEB"
if [ -n "${1:-}" ]; then
  echo "Installing to $1 ..."
  make install THEOS_DEVICE_IP="$1"
fi
