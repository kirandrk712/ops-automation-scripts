#!/usr/bin/env python3
"""Concurrent HTTP health checker (standard library only).

Reads URLs from a file (one per line, '#' for comments) or the command line,
reports status code and latency, and exits non-zero if any endpoint is unhealthy.

Examples:
    ./http_health_check.py https://example.com https://example.org/health
    ./http_health_check.py -f endpoints.txt --timeout 5 --expect 200
"""
import argparse
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def check(url: str, timeout: float, expect: int) -> tuple:
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception as exc:  # DNS failure, timeout, TLS error...
        return url, None, (time.perf_counter() - start) * 1000, str(exc)
    elapsed = (time.perf_counter() - start) * 1000
    return url, code, elapsed, "" if code == expect else f"expected {expect}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("urls", nargs="*")
    parser.add_argument("-f", "--file", help="file containing URLs")
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--expect", type=int, default=200)
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    urls = list(args.urls)
    if args.file:
        with open(args.file) as fh:
            urls += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    if not urls:
        parser.error("no URLs supplied")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda u: check(u, args.timeout, args.expect), urls))

    failed = 0
    for url, code, ms, err in results:
        ok = not err
        failed += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {url} status={code} time={ms:.0f}ms {err}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
