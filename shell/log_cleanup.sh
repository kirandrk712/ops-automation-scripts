#!/usr/bin/env bash
# Delete (or compress) old log files safely. Dry-run by default.
# Usage: ./log_cleanup.sh -d /var/log/myapp [-a 14] [-z] [-x]
#   -d  directory to clean (required)
#   -a  age in days (default 14)
#   -z  compress *.log files older than age instead of deleting
#   -x  actually perform the action (otherwise dry-run)
set -euo pipefail

DIR=""; DAYS=14; COMPRESS=0; EXEC=0
while getopts "d:a:zx" opt; do
  case $opt in
    d) DIR=$OPTARG ;;
    a) DAYS=$OPTARG ;;
    z) COMPRESS=1 ;;
    x) EXEC=1 ;;
    *) exit 2 ;;
  esac
done

[ -n "$DIR" ] || { echo "-d <dir> is required" >&2; exit 2; }
[ -d "$DIR" ] || { echo "not a directory: $DIR" >&2; exit 2; }
case "${DIR%/}" in ""|/etc|/usr|/bin|/boot|/var) echo "refusing to touch $DIR" >&2; exit 2 ;; esac

if [ "$COMPRESS" -eq 1 ]; then
  files=$(find "$DIR" -type f -name '*.log' -mtime +"$DAYS")
else
  files=$(find "$DIR" -type f -name '*.log*' -mtime +"$DAYS")
fi

[ -n "$files" ] || { echo "Nothing older than $DAYS days in $DIR"; exit 0; }

count=$(echo "$files" | wc -l)
echo "$count file(s) older than $DAYS days in $DIR"
echo "$files" | head -20

if [ "$EXEC" -eq 0 ]; then
  echo "(dry-run - pass -x to execute)"
  exit 0
fi

if [ "$COMPRESS" -eq 1 ]; then
  echo "$files" | xargs -r gzip -9
  echo "Compressed $count file(s)"
else
  echo "$files" | xargs -r rm -f --
  echo "Deleted $count file(s)"
fi
