# ops-automation-scripts

[![CI](https://github.com/kirandrk712/ops-automation-scripts/actions/workflows/ci.yml/badge.svg)](https://github.com/kirandrk712/ops-automation-scripts/actions/workflows/ci.yml)

Python and Bash tools for the situations operations engineers actually face: a deploy just went out, a disk is filling, a certificate is about to expire, errors are spiking. Each tool is **tested**, **safe by default** (dry-runs, protected paths, restart caps) and **scriptable** (meaningful exit codes, JSON output).

## "When X happens, I reach for..."

| Situation | Tool | Notes |
|---|---|---|
| A deploy just finished - is it healthy? | `python/release_gate.py` | Needs N consecutive healthy checks (status + latency). Prints `ROLLBACK_REQUIRED` and exits 1 otherwise. Used by the pipeline in [azure-pipelines-templates](../azure-pipelines-templates). |
| Error rate is spiking - what, where, since when? | `python/log_analyzer.py` | Status mix, 5xx rate, worst minute, top failing paths and IPs, p95 request time. `--max-error-rate` makes it a pass/fail check. |
| Disk is filling up | `python/disk_usage_alert.py`, `shell/log_cleanup.sh` | Nagios-style exit codes + JSON; cleanup is dry-run by default and refuses system directories. |
| A certificate is about to expire | `python/ssl_cert_expiry.py` | Warn/crit thresholds, custom CA support, many hosts at once. |
| Are all my endpoints up? | `python/http_health_check.py` | Concurrent checks with status and latency. |
| What do we even have running in AWS? | `python/aws_ec2_inventory.py` | Multi-region EC2 inventory to CSV (boto3). |
| A server "feels slow" | `shell/linux_health_check.sh` | Load vs cores, memory, disk, failed units, zombies, top consumers. |
| A service keeps dying overnight | `shell/service_watchdog.sh` | Restarts with a cap, keeps a log trail, captures journal on failure. |

## Example: gating a release

```bash
python3 python/release_gate.py \
  --url https://app.example.com/health --url https://app.example.com/api/ping \
  --checks 5 --interval 3 --timeout 120 --max-latency-ms 800 \
  || ./rollback.sh          # RELEASE_HEALTHY -> 0, ROLLBACK_REQUIRED -> 1
```

## Example: triaging errors from a log

```bash
$ python3 python/log_analyzer.py /var/log/nginx/access.log --top 3
Requests: 48210  (unparsed lines: 0)
Status classes: {'2xx': 45102, '3xx': 1210, '4xx': 1380, '5xx': 518}
5xx rate: 1.07%
Worst minute for 5xx: 10/Oct/2026:13:56 (203 errors)
Top 5xx paths: [('/api/pay', 471), ('/api/orders', 47)]
```

(Illustrative output.)

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The suite includes a real TLS handshake against a locally generated certificate, a live HTTP server for the release gate, and end-to-end runs of the cleanup script. CI also runs `shellcheck`.

## Conventions

- `set -euo pipefail` in Bash; argparse + small testable functions in Python (no third-party deps except boto3 for the inventory script).
- Exit codes: `0` OK, `1` warning/failure, `2` critical or misuse.
