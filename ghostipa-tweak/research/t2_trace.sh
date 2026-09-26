#!/bin/sh
# T2 — search network trace. Confirms the results-array merge point.
# Run on-device as root while performing one App Store search.
# Uses rvictl remote virtual interface + tcpdump; NO SSL bypass involved —
# we only need URL hosts + timing to locate the merge, not payload contents.
set -e
IFACE=${1:-rvi0}
OUT=/var/mobile/Library/GhostIPA/T2-search.pcap
mkdir -p "$(dirname "$OUT")"
echo "[T2] Capturing 60s on $IFACE — perform ONE App Store search now."
echo "[T2] Hosts of interest: *.itunes.apple.com, *.mzstatic.com, *.apple.com"
tcpdump -i "$IFACE" -w "$OUT" -s 256 host itunes.apple.com or host search.itunes.apple.com or host mzstatic.com &
PID=$!
sleep 60
kill -INT $PID || true
echo "[T2] Saved $OUT — open in Wireshark, note request path + response time."
echo "[T2] The merge point is the code that fires ~0-2s after the lookup response."
