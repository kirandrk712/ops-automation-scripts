#!/usr/bin/env bash
# Restart systemd services that are down, with a log trail and a restart cap.
# Usage: ./service_watchdog.sh nginx docker chronyd
# Cron:  */5 * * * * /opt/scripts/service_watchdog.sh nginx >> /var/log/service_watchdog.log 2>&1
set -uo pipefail

MAX_RESTARTS="${MAX_RESTARTS:-3}"
STATE_DIR="${STATE_DIR:-/var/tmp/service_watchdog}"
mkdir -p "$STATE_DIR"
ts() { date '+%F %T'; }

[ "$#" -gt 0 ] || { echo "usage: $0 service [service...]" >&2; exit 2; }

rc=0
for svc in "$@"; do
  state_file="$STATE_DIR/$svc.count"
  if systemctl is-active --quiet "$svc"; then
    rm -f "$state_file"
    continue
  fi

  count=$(cat "$state_file" 2>/dev/null || echo 0)
  if [ "$count" -ge "$MAX_RESTARTS" ]; then
    echo "$(ts) [$svc] DOWN - restart cap ($MAX_RESTARTS) reached, escalate manually"
    rc=2
    continue
  fi

  echo "$(ts) [$svc] DOWN - restart attempt $((count + 1))/$MAX_RESTARTS"
  echo $((count + 1)) > "$state_file"
  systemctl restart "$svc" || true
  sleep 3
  if systemctl is-active --quiet "$svc"; then
    echo "$(ts) [$svc] recovered"
  else
    echo "$(ts) [$svc] restart FAILED"
    journalctl -u "$svc" -n 10 --no-pager 2>/dev/null || true
    rc=1
  fi
done
exit "$rc"
