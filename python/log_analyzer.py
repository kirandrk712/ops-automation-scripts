#!/usr/bin/env python3
"""Summarise an nginx/Apache access log: status mix, error rate, noisy paths/IPs, 5xx spikes.

Understands the 'combined' format, optionally followed by $request_time as the last field.
Exit code 2 if the 5xx rate exceeds --max-error-rate (handy as a post-deploy check).

Examples:
    ./log_analyzer.py /var/log/nginx/access.log
    ./log_analyzer.py access.log --top 10 --max-error-rate 2 --json
"""
import argparse
import json
import re
import sys
from collections import Counter

LINE = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+)[^"]*" '
    r'(?P<status>\d{3}) (?P<size>\S+)(?: "[^"]*" "[^"]*")?(?: (?P<rt>\d+(?:\.\d+)?))?\s*$'
)


def parse(lines):
    bad = 0
    for line in lines:
        m = LINE.match(line)
        if not m:
            bad += 1
            continue
        d = m.groupdict()
        yield {
            "ip": d["ip"],
            "minute": d["ts"][:17],             # 10/Oct/2026:13:55
            "path": d["path"].split("?")[0],
            "status": int(d["status"]),
            "rt": float(d["rt"]) if d["rt"] else None,
        }
    parse.bad = bad


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct / 100 * (len(ordered) - 1))))]


def analyse(lines, top=5):
    total = 0
    classes, ips, err_paths, err_by_min = Counter(), Counter(), Counter(), Counter()
    times = []
    for r in parse(lines):
        total += 1
        classes[f"{r['status'] // 100}xx"] += 1
        ips[r["ip"]] += 1
        if r["status"] >= 500:
            err_paths[r["path"]] += 1
            err_by_min[r["minute"]] += 1
        if r["rt"] is not None:
            times.append(r["rt"])
    errors = classes.get("5xx", 0)
    spike = err_by_min.most_common(1)
    return {
        "total_requests": total,
        "unparsed_lines": getattr(parse, "bad", 0),
        "status_classes": dict(sorted(classes.items())),
        "error_rate_pct": round(errors / total * 100, 2) if total else 0.0,
        "top_5xx_paths": err_paths.most_common(top),
        "top_client_ips": ips.most_common(top),
        "worst_5xx_minute": spike[0] if spike else None,
        "p95_request_time_s": percentile(times, 95),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("logfile")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--max-error-rate", type=float, help="exit 2 if 5xx%% exceeds this")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    with open(args.logfile, errors="replace") as fh:
        result = analyse(fh, args.top)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Requests: {result['total_requests']}  (unparsed lines: {result['unparsed_lines']})")
        print(f"Status classes: {result['status_classes']}")
        print(f"5xx rate: {result['error_rate_pct']}%")
        if result["worst_5xx_minute"]:
            print(f"Worst minute for 5xx: {result['worst_5xx_minute'][0]} ({result['worst_5xx_minute'][1]} errors)")
        if result["p95_request_time_s"] is not None:
            print(f"p95 request time: {result['p95_request_time_s']}s")
        print("Top 5xx paths:", result["top_5xx_paths"] or "none")
        print("Top client IPs:", result["top_client_ips"])

    if args.max_error_rate is not None and result["error_rate_pct"] > args.max_error_rate:
        print(f"FAIL: 5xx rate {result['error_rate_pct']}% > {args.max_error_rate}%", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
