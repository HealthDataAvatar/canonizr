#!/usr/bin/env bash
# Measures event loop responsiveness during a heavy conversion.
#
# Sends 1 heavy conversion request, then polls /health every 200ms
# throughout. Reports health latency stats. If the event loop is
# blocked by a synchronous call, health responses will spike or timeout.

set -euo pipefail

now_ms() { python3 -c 'import time; print(int(time.time()*1000))'; }

GATEWAY="${GATEWAY_URL:-http://localhost:7005}"
FIXTURE="${1:-$(dirname "$0")/../gateway/tests/fixtures/heavy.docx}"
POLL_INTERVAL_MS=200
HEALTH_TIMEOUT_MS=2000

if [[ ! -f "$FIXTURE" ]]; then
  echo "ERROR: fixture not found: $FIXTURE" >&2
  exit 1
fi

echo "=== Event Loop Responsiveness Test ==="
echo "Gateway:  $GATEWAY"
echo "Fixture:  $FIXTURE"
echo ""

# --- Pre-test health check ---
echo "Pre-test health check..."
if ! curl -sf "$GATEWAY/health" > /dev/null 2>&1; then
  echo "ERROR: gateway not healthy at $GATEWAY/health" >&2
  exit 1
fi
echo "OK"
echo ""

TMPDIR=$(mktemp -d)
trap 'rm -rf "$TMPDIR"' EXIT

# --- Start 1 heavy conversion in background ---
echo "Starting conversion..."
CONVERT_START=$(now_ms)
curl -s -o "$TMPDIR/convert_out.txt" -w "%{http_code}" \
  -X POST -F "file=@$FIXTURE" "$GATEWAY/convert" > "$TMPDIR/convert_code.txt" &
CONVERT_PID=$!

# --- Poll /health until conversion finishes ---
POLL_COUNT=0
HEALTH_LOG="$TMPDIR/health_latencies.txt"

while kill -0 "$CONVERT_PID" 2>/dev/null; do
  H_START=$(now_ms)
  H_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --max-time "$(echo "scale=1; $HEALTH_TIMEOUT_MS/1000" | bc)" \
    "$GATEWAY/health" 2>/dev/null || echo "000")
  H_END=$(now_ms)
  H_ELAPSED=$(( H_END - H_START ))
  echo "$H_ELAPSED $H_CODE" >> "$HEALTH_LOG"
  POLL_COUNT=$((POLL_COUNT + 1))

  # Sleep between polls
  python3 -c "import time; time.sleep($POLL_INTERVAL_MS / 1000)"
done

wait "$CONVERT_PID" || true
CONVERT_END=$(now_ms)
CONVERT_ELAPSED=$(( CONVERT_END - CONVERT_START ))
CONVERT_CODE=$(cat "$TMPDIR/convert_code.txt" 2>/dev/null || echo "???")

# --- Compute stats ---
echo ""
echo "=== Results ==="
echo "Conversion: HTTP $CONVERT_CODE in ${CONVERT_ELAPSED}ms"
echo "Health polls: $POLL_COUNT"

if [[ ! -s "$HEALTH_LOG" ]]; then
  echo "No health polls recorded (conversion was too fast)."
  exit 0
fi

echo ""
echo "Health latencies (ms):"
python3 -c "
import sys

latencies = []
timeouts = 0
for line in open('$HEALTH_LOG'):
    ms, code = line.strip().split()
    ms = int(ms)
    latencies.append(ms)
    if code == '000' or ms >= $HEALTH_TIMEOUT_MS:
        timeouts += 1

latencies.sort()
n = len(latencies)
p50 = latencies[n // 2]
p99 = latencies[int(n * 0.99)]
mx = latencies[-1]
mn = latencies[0]
blocked = sum(1 for l in latencies if l > 1000)

print(f'  min:  {mn}ms')
print(f'  p50:  {p50}ms')
print(f'  p99:  {p99}ms')
print(f'  max:  {mx}ms')
print(f'  timeouts (>{$HEALTH_TIMEOUT_MS}ms): {timeouts}/{n}')
print(f'  blocked (>1s): {blocked}/{n}')
print()
if blocked > 0 or timeouts > 0:
    print('FAIL: event loop was blocked during conversion')
    sys.exit(1)
else:
    print('PASS: event loop stayed responsive')
"
