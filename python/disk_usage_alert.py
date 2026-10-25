#!/usr/bin/env python3
"""Check disk usage on one or more mount points and exit non-zero on breach.

Exit codes: 0 = OK, 1 = warning, 2 = critical (Nagios-style, easy to wire into cron/monitoring).

Examples:
    ./disk_usage_alert.py
    ./disk_usage_alert.py -m / /var /data --warn 75 --crit 90 --json
"""
import argparse
import json
import shutil
import sys


def check_mount(path: str, warn: int, crit: int) -> dict:
    usage = shutil.disk_usage(path)
    pct = round(usage.used / usage.total * 100, 1)
    status = "CRITICAL" if pct >= crit else "WARNING" if pct >= warn else "OK"
    return {
        "mount": path,
        "used_pct": pct,
        "free_gb": round(usage.free / 1024**3, 2),
        "total_gb": round(usage.total / 1024**3, 2),
        "status": status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("-m", "--mounts", nargs="+", default=["/"])
    parser.add_argument("--warn", type=int, default=80)
    parser.add_argument("--crit", type=int, default=90)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args()

    results = []
    for mount in args.mounts:
        try:
            results.append(check_mount(mount, args.warn, args.crit))
        except OSError as exc:
            results.append({"mount": mount, "status": "CRITICAL", "error": str(exc)})

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            if "error" in r:
                print(f"CRITICAL {r['mount']}: {r['error']}")
            else:
                print(f"{r['status']:<8} {r['mount']:<15} {r['used_pct']:>5}% used, {r['free_gb']} GB free")

    statuses = {r["status"] for r in results}
    if "CRITICAL" in statuses:
        return 2
    if "WARNING" in statuses:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
