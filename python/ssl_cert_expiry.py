#!/usr/bin/env python3
"""Check TLS certificate expiry for one or more host[:port] targets.

Exit codes: 0 OK, 1 expiring within --warn days, 2 expiring within --crit days or unreachable/invalid.

Examples:
    ./ssl_cert_expiry.py example.com api.example.com:8443
    ./ssl_cert_expiry.py -f hosts.txt --warn 30 --crit 14
    ./ssl_cert_expiry.py internal.local --cafile corp-ca.pem
"""
import argparse
import socket
import ssl
import sys
import time


def days_remaining(host, port=443, timeout=5.0, cafile=None):
    ctx = ssl.create_default_context(cafile=cafile)
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    expires = ssl.cert_time_to_seconds(cert["notAfter"])
    return (expires - time.time()) / 86400


def split_target(target):
    host, _, port = target.partition(":")
    return host, int(port) if port else 443


def classify(days, warn, crit):
    if days < 0:
        return "EXPIRED", 2
    if days < crit:
        return "CRITICAL", 2
    if days < warn:
        return "WARNING", 1
    return "OK", 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("targets", nargs="*")
    ap.add_argument("-f", "--file", help="file with one host[:port] per line")
    ap.add_argument("--warn", type=int, default=30)
    ap.add_argument("--crit", type=int, default=14)
    ap.add_argument("--cafile", help="custom CA bundle (for internal CAs)")
    a = ap.parse_args()

    targets = list(a.targets)
    if a.file:
        with open(a.file) as fh:
            targets += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    if not targets:
        ap.error("no targets supplied")

    worst = 0
    for t in targets:
        host, port = split_target(t)
        try:
            days = days_remaining(host, port, cafile=a.cafile)
            status, rc = classify(days, a.warn, a.crit)
            print(f"{status:<9} {t:<35} {days:7.1f} days left")
        except (OSError, ssl.SSLError) as exc:
            status, rc = "ERROR", 2
            print(f"{status:<9} {t:<35} {exc}")
        worst = max(worst, rc)
    return worst


if __name__ == "__main__":
    sys.exit(main())
