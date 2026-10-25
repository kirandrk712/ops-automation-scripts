# ops-automation-scripts

Practical Python and Bash utilities for day-to-day operations work. They're built to be safe by default (dry-runs, restart caps, protected paths) and scriptable (meaningful exit codes, JSON output).

## Python (`python/`)

| Script | What it does | Deps |
|--------|--------------|------|
| `disk_usage_alert.py` | Checks mount points against warn/crit thresholds. Nagios-style exit codes, optional JSON. | stdlib |
| `http_health_check.py` | Concurrent endpoint checker with status + latency. | stdlib |
| `aws_ec2_inventory.py` | Exports EC2 inventory across regions to CSV (paginated). | boto3 |

```bash
python3 python/disk_usage_alert.py -m / /var --warn 75 --crit 90 --json
python3 python/http_health_check.py https://example.com --expect 200
pip install -r requirements.txt && python3 python/aws_ec2_inventory.py --all-regions
```

## Shell (`shell/`)

| Script | What it does |
|--------|--------------|
| `linux_health_check.sh` | Load, memory, disk, failed units, zombies, top consumers; exits 1 on warnings. |
| `log_cleanup.sh` | Deletes or gzips old logs. **Dry-run by default**, refuses system directories. |
| `service_watchdog.sh` | Restarts downed systemd services with a restart cap and journal excerpt. Cron-friendly. |

```bash
./shell/linux_health_check.sh 80 85
./shell/log_cleanup.sh -d /var/log/myapp -a 14        # preview
./shell/log_cleanup.sh -d /var/log/myapp -a 14 -z -x  # compress for real
```

## Conventions

- `set -euo pipefail` in Bash; argparse + type-hinted functions in Python.
- Exit codes: `0` OK, `1` warning/failure, `2` critical or misuse.
- Lint with `shellcheck shell/*.sh` and `python3 -m pyflakes python/`.
