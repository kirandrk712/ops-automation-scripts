#!/usr/bin/env python3
"""Post-deployment gate: require N consecutive healthy checks before declaring a release good.

Exits 0 when healthy, 1 when the deadline passes first. On failure it prints ROLLBACK_REQUIRED so a
pipeline step (or a human) can trigger the rollback.

Examples:
    ./release_gate.py --url https://app.example.com/health
    ./release_gate.py --url http://a/health --url http://b/health --checks 5 --interval 2 --timeout 90 --max-latency-ms 800
"""
import argparse
import sys
import time
import urllib.error
import urllib.request


def check_once(url, expect, max_latency_ms, timeout=5.0):
    """Return (healthy, message)."""
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            code = resp.status
    except urllib.error.HTTPError as exc:
        code = exc.code
    except Exception as exc:
        return False, f"{url}: {type(exc).__name__}: {exc}"
    ms = (time.perf_counter() - start) * 1000
    if code != expect:
        return False, f"{url}: status {code}, expected {expect}"
    if max_latency_ms and ms > max_latency_ms:
        return False, f"{url}: {ms:.0f}ms exceeds {max_latency_ms:.0f}ms"
    return True, f"{url}: {code} in {ms:.0f}ms"


def gate(urls, checks=5, interval=2.0, timeout=120.0, expect=200, max_latency_ms=None,
         check=check_once, sleep=time.sleep, clock=time.monotonic, log=print):
    """Poll until `checks` consecutive rounds are healthy across all URLs, or `timeout` elapses."""
    deadline = clock() + timeout
    streak = 0
    while clock() < deadline:
        results = [check(u, expect, max_latency_ms) for u in urls]
        if all(ok for ok, _ in results):
            streak += 1
            log(f"healthy {streak}/{checks}: " + "; ".join(msg for _, msg in results))
            if streak >= checks:
                return True
        else:
            streak = 0
            log("unhealthy, streak reset: " + "; ".join(msg for ok, msg in results if not ok))
        sleep(interval)
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--url", action="append", required=True)
    ap.add_argument("--checks", type=int, default=5, help="consecutive healthy rounds required")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--expect", type=int, default=200)
    ap.add_argument("--max-latency-ms", type=float)
    a = ap.parse_args()

    if gate(a.url, a.checks, a.interval, a.timeout, a.expect, a.max_latency_ms):
        print("RELEASE_HEALTHY")
        return 0
    print("ROLLBACK_REQUIRED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
