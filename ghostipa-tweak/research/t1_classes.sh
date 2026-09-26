#!/bin/sh
# T1 — runtime class discovery. Run on-device as root (jailbroken).
# Dumps AppStore.app ObjC classes matching Ghost-relevant patterns.
# Output: /var/mobile/Library/GhostIPA/T1-classes.txt
set -e
OUT=/var/mobile/Library/GhostIPA/T1-classes.txt
mkdir -p "$(dirname "$OUT")"
echo "=== T1 $(date) iOS $(sw_vers -productVersion 2>/dev/null || uname -r) ===" > "$OUT"

# Path 1: class-dump binary if present (Cydia class-dump / classdump-dyld).
if command -v class-dump >/dev/null 2>&1; then
  BIN=$(find /Applications/AppStore.app /private/var/containers/Bundle/Application -maxdepth 4 -name AppStore -type f 2>/dev/null | head -1)
  echo "binary: $BIN" >> "$OUT"
  class-dump -H "$BIN" -o /tmp/GhostT1 2>/dev/null
  grep -rilE 'Search|ProductPage|ProductLockup|Storefront|PurchaseHistory|Availability|DownloadManager' /tmp/GhostT1 2>/dev/null >> "$OUT" || true
fi

# Path 2: runtime dump via objc — works without class-dump, logs to syslog.
# Compile on builder: clang -framework Foundation -framework ObjectiveC t1_dump.m -o t1_dump
# Run: ./t1_dump com.apple.AppStore  → same OUT file.
echo "---" >> "$OUT"
echo "If class-dump absent, build+run research/t1_dump.m (runtime objc path)." >> "$OUT"
echo "Then grep this file for Search|Product|Storefront|Purchase|Download|Availability" >> "$OUT"
cat "$OUT"
