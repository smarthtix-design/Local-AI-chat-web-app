#!/bin/bash
# Restarts the web server (or Ollama) when /health fails 3 checks in a row. Run every minute by a systemd timer.
URL="${HEALTH_URL:-http://127.0.0.1:8000/health}"
DIR="${STATE_DIR:-/var/tmp}"
SYSTEMCTL="${SYSTEMCTL:-systemctl}"
LIMIT="${FAIL_LIMIT:-3}"
bump() {   # bump <name> <ok 0/1> <service>
  local f="$DIR/tinychat-fail-$1" n=0
  [ -f "$f" ] && n=$(cat "$f")
  if [ "$2" = "1" ]; then echo 0 > "$f"; return; fi
  n=$((n + 1)); echo "$n" > "$f"
  if [ "$n" -ge "$LIMIT" ]; then echo "$(date '+%F %T') $1 unhealthy $n times: restarting $3"; "$SYSTEMCTL" restart "$3"; echo 0 > "$f"; fi
}
resp=$(curl -s -m 10 "$URL")
web=0; ollama=0
echo "$resp" | grep -q '"ok": true' && web=1
echo "$resp" | grep -q '"ollama": true' && ollama=1
bump web "$web" tinychat
[ "$web" = "1" ] && bump ollama "$ollama" ollama
exit 0
