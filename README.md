# Linux Health Dashboard

![linux-health-dashboard project banner](docs/project-banner.webp)

A read-only, localhost dashboard for Linux memory, disk usage, uptime, load averages, selected systemd services, and Docker containers. Built as a new learning and portfolio project for Jason Edwards; it has not been deployed or validated on his home server.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![Dependencies](https://img.shields.io/badge/runtime-standard_library-green)

## Try it

Requires Python 3.11 or newer. Live host metrics require Linux; demo mode works without Docker or systemd.

```bash
python3 dashboard.py --demo
# Open http://127.0.0.1:8765
```

For real host data:

```bash
python3 dashboard.py --services docker.service ssh.service --disk /
```

On Fedora, the SSH unit is commonly `sshd.service`; choose names that exist on your host. No services are queried by default. The program reads `/proc/meminfo` and `/proc/uptime`, uses filesystem statistics, runs `systemctl is-active` for your selected units, and runs `docker ps -a`. It never starts or stops services or containers. CPU **load averages**, rather than a CPU utilization percentage, are shown.

## Design

One background collector updates a cached snapshot every 15 seconds. The HTTP server serves the UI at `/` and the JSON snapshot at `/api/health`. Requests cannot supply commands or arbitrary file paths. The UI uses text nodes for service and container names.

| Route | Behavior |
| --- | --- |
| `/` | Responsive dashboard |
| `/api/health` | JSON metrics; 503 while starting or if collection fails |
| Other paths | 404 |

The browser refreshes every 15 seconds. `--interval` controls collection independently, with a minimum of 5 seconds. Each subprocess has a 3-second timeout; at most 8 services can be configured. Collection is sequential, so unresponsive commands can increase snapshot age. The capture timestamp is visible, and fetch failures leave an explicit stale-data warning.

Docker access depends on your user's existing permissions. An inaccessible daemon is reported as unavailable, not as zero containers. Do not grant new Docker privileges solely for this demo; Docker group access is powerful. Missing Linux `/proc` metrics appear as unavailable. Disk-path errors make the collector return 503.

## Remote viewing

The server deliberately binds to `127.0.0.1` and has no authentication. View a remote server through an SSH tunnel, adjusting the account and host:

```bash
ssh -L 8765:127.0.0.1:8765 YOUR_USER@YOUR_SERVER
```

Then open http://127.0.0.1:8765 on your computer. Keep the Python process running on the server. Stop it with Ctrl+C. Do not reverse proxy it publicly without adding authentication and TLS.

## Validation

```bash
python3 -m unittest discover -s tests -v
```

Four automated tests cover memory accounting, unavailable Docker/systemd, the HTTP JSON route, and rejection of arbitrary file serving. Tests use controlled fixtures for unavailable services; they do not prove compatibility with every Docker or systemd version. `demo.json` contains fictional service/container data, never a capture of a personal server.

## What this demonstrates

Linux `/proc` metrics, subprocess timeouts, degraded-service reporting, a background collection loop, HTTP/JSON, defensive UI rendering, and unit/HTTP tests. It does not demonstrate historical alerting, multi-host monitoring, or production deployment experience.
