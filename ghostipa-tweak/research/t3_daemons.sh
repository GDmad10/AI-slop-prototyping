#!/bin/sh
# T3 — daemon ownership map. Confirms appstored owns downloads (hands off!)
# and finds which process hosts search/purchase-history. Read-only: ps + launchctl.
set -e
OUT=/var/mobile/Library/GhostIPA/T3-daemons.txt
mkdir -p "$(dirname "$OUT")"
{
echo "=== T3 $(date) ==="
echo "--- store/download daemons ---"
ps aux | grep -iE 'appstored|itunesstored|storebookkeeperd|mediaassetd|nsurlsessiond' | grep -v grep || true
echo "--- AppStore + Preferences procs ---"
ps aux | grep -iE 'AppStore|Preferences' | grep -v grep || true
echo "--- purchase-history related ---"
ps aux | grep -iE 'account|purchase|store' | grep -v grep | head -20 || true
echo "=== RULE: Ghost hooks search/PDP presentation only. Daemons above are OFF-LIMITS. ==="
} | tee "$OUT"
