"""Read-only Linux metrics, served on localhost; Python standard library only."""
import argparse
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).parent


def memory_info(text):
    values = {}
    for line in text.splitlines():
        key, value = line.split(':', 1)
        values[key] = int(value.split()[0]) * 1024
    total = values['MemTotal']
    available = values.get('MemAvailable', values.get('MemFree', 0))
    return {'total': total, 'used': total - available,
            'percent': round((total - available) / total * 100, 1)}


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=False)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return None, ''


def services_info(names):
    items = []
    for name in names:
        code, out = command(['systemctl', 'is-active', '--', name])
        state = out.strip()
        items.append({'name': name, 'state': state if state in
                      {'active', 'inactive', 'failed', 'activating', 'deactivating'}
                      else 'unavailable'})
    return items


def containers_info():
    code, output = command(['docker', 'ps', '-a', '--format', '{{json .}}'])
    if code != 0:
        return {'available': False, 'items': [],
                'note': 'Docker missing, inaccessible, or not running'}
    try:
        items = [json.loads(line) for line in output.splitlines() if line.strip()]
        return {'available': True, 'items': [
            {'name': x.get('Names', ''), 'image': x.get('Image', ''),
             'state': x.get('State', ''), 'status': x.get('Status', '')} for x in items]}
    except (ValueError, AttributeError):
        return {'available': False, 'items': [], 'note': 'Unexpected Docker response'}


def snapshot(disk_path='/', services=()):
    disk = shutil.disk_usage(disk_path)
    try:
        memory = memory_info(Path('/proc/meminfo').read_text())
        uptime = int(float(Path('/proc/uptime').read_text().split()[0]))
        load = list(os.getloadavg())
    except (OSError, ValueError, KeyError, AttributeError):
        memory, uptime, load = None, None, None
    return {'captured_at': datetime.now(timezone.utc).isoformat(),
            'disk': {'path': disk_path, 'total': disk.total, 'used': disk.used,
                     'percent': round(disk.used / disk.total * 100, 1)},
            'memory': memory, 'uptime_seconds': uptime, 'load': load,
            'cpu_count': os.cpu_count(), 'services': services_info(services),
            'containers': containers_info(), 'demo': False}


class Collector:
    def __init__(self, interval, disk, services, demo):
        self.interval, self.disk, self.services, self.demo = interval, disk, services, demo
        self.data = None
        self.lock = threading.Lock()

    def collect(self):
        while True:
            try:
                data = json.loads((ROOT / 'demo.json').read_text()) if self.demo else snapshot(self.disk, self.services)
                data['captured_at'] = datetime.now(timezone.utc).isoformat()
                with self.lock:
                    self.data = data
            except Exception:
                with self.lock:
                    self.data = {'error': 'Collection failed; check disk path and permissions'}
            time.sleep(self.interval)


def handler_for(collector):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/':
                body, kind, status = (ROOT / 'index.html').read_bytes(), 'text/html; charset=utf-8', 200
            elif self.path == '/api/health':
                with collector.lock:
                    data = collector.data
                status = 200 if data and 'error' not in data else 503
                body, kind = json.dumps(data or {'error': 'Starting collector'}).encode(), 'application/json'
            else:
                body, kind, status = b'Not found', 'text/plain', 404
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--disk', default='/')
    parser.add_argument('--services', nargs='*', default=[])
    parser.add_argument('--interval', type=int, default=15)
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    if args.interval < 5 or len(args.services) > 8:
        parser.error('Use an interval of at least 5 seconds and at most 8 services')
    collector = Collector(args.interval, args.disk, args.services, args.demo)
    threading.Thread(target=collector.collect, daemon=True).start()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(collector))
    print(f'Linux Health Dashboard: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
