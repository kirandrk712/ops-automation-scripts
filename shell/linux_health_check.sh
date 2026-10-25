#!/usr/bin/env bash
# Quick Linux health snapshot: load, memory, disk, failed units, zombies, top consumers.
# Usage: ./linux_health_check.sh [disk_warn_pct] [mem_warn_pct]
set -uo pipefail

DISK_WARN="${1:-80}"
MEM_WARN="${2:-85}"
rc=0

section() { printf '\n== %s ==\n' "$1"; }
warn()    { printf 'WARN: %s\n' "$1"; rc=1; }

section "Host"
echo "$(hostname) | $(uname -sr) | $(uptime -p 2>/dev/null || uptime)"

section "Load average"
read -r l1 l5 l15 _ < /proc/loadavg
cores=$(nproc)
echo "1m=$l1 5m=$l5 15m=$l15 (cores: $cores)"
awk -v l="$l5" -v c="$cores" 'BEGIN{exit !(l > c)}' && warn "5-minute load exceeds core count"

section "Memory"
mem_pct=$(free | awk '/^Mem:/ {printf "%d", ($3/$2)*100}')
free -h | head -2
[ "$mem_pct" -ge "$MEM_WARN" ] && warn "memory usage ${mem_pct}% >= ${MEM_WARN}%"

section "Disk"
df -hP -x tmpfs -x devtmpfs
while read -r pct mount; do
  [ "${pct%\%}" -ge "$DISK_WARN" ] && warn "$mount is ${pct} full"
done < <(df -P -x tmpfs -x devtmpfs | awk 'NR>1 {print $5, $6}')

section "Failed systemd units"
if command -v systemctl >/dev/null 2>&1; then
  failed=$(systemctl --failed --no-legend --plain 2>/dev/null)
  if [ -n "$failed" ]; then echo "$failed"; warn "failed units present"; else echo "none"; fi
else
  echo "systemctl not available"
fi

section "Zombie processes"
zombies=$(ps -eo stat | grep -c '^Z' || true)
echo "$zombies"
[ "$zombies" -gt 0 ] && warn "$zombies zombie process(es)"

section "Top 5 by CPU"
ps -eo pid,user,%cpu,%mem,comm --sort=-%cpu | head -6

section "Top 5 by memory"
ps -eo pid,user,%cpu,%mem,comm --sort=-%mem | head -6

echo
if [ "$rc" -eq 0 ]; then echo "RESULT: healthy"; else echo "RESULT: warnings found"; fi
exit "$rc"
