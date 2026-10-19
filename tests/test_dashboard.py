import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen
from http.server import ThreadingHTTPServer
import dashboard


class DashboardTests(unittest.TestCase):
    def test_available_memory_includes_reclaimable_cache(self):
        data = dashboard.memory_info('MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 600 kB\n')
        self.assertEqual(data['percent'], 40)

    def test_docker_permission_failure_does_not_claim_empty_host(self):
        with patch.object(dashboard, 'command', return_value=(1, '')):
            self.assertFalse(dashboard.containers_info()['available'])

    def test_systemctl_missing_is_unavailable(self):
        with patch.object(dashboard, 'command', return_value=(None, '')):
            self.assertEqual(dashboard.services_info(['ssh.service'])[0]['state'], 'unavailable')

    def test_http_json_and_no_arbitrary_file_serving(self):
        collector = dashboard.Collector(15, '/', [], True)
        collector.data = json.loads((Path(dashboard.__file__).parent / 'demo.json').read_text())
        server = ThreadingHTTPServer(('127.0.0.1', 0), dashboard.handler_for(collector))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/api/health') as response:
                self.assertTrue(json.load(response)['demo'])
            from urllib.error import HTTPError
            with self.assertRaises(HTTPError) as error:
                urlopen(f'http://127.0.0.1:{server.server_port}/demo.json')
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
