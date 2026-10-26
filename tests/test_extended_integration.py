"""Portable end-to-end tests using only a local HTTP server (no Internet)."""
from contextlib import redirect_stdout, redirect_stderr
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

import cli
from models import CheckResult


class LabHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        statuses = {
            '/': 200,
            '/created': 201,
            '/empty': 204,
            '/redirect': 302,
            '/auth': 401,
            '/forbidden': 403,
            '/missing': 404,
            '/teapot': 418,
            '/error': 503,
        }
        status = statuses.get(self.path, 404)
        self.send_response(status)
        if status == 302:
            self.send_header('Location', '/')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def log_message(self, *_args):
        pass  # Keep automated test logs focused on assertions.


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), LabHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def run_diagnostic(self, path='/', *, only='all', output=None):
        self.assertIsNotNone(output)
        url = f'http://127.0.0.1:{self.port}{path}'
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            code = cli.main([
                '--host', '127.0.0.1', '--port', str(self.port),
                '--url', url, '--only', only,
                '--timeout', '2', '--output', str(output),
            ])
        records = [json.loads(s) for s in output.read_text(encoding='utf-8').splitlines()]
        return code, records[-1]

    def test_all_checks_healthy(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic(output=Path(temp) / 'diag.jsonl')
        self.assertEqual(code, 0)
        self.assertEqual([r['check'] for r in rec['results']], ['dns', 'tcp', 'http'])
        self.assertTrue(rec['overall_success'])
        self.assertEqual(rec['diagnosis']['code'], 'checks_passed')

    def test_created_is_http_success(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/created', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 0)
        self.assertEqual(rec['results'][-1]['details']['status_code'], 201)

    def test_no_content_is_http_success(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/empty', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 0)
        self.assertEqual(rec['results'][-1]['details']['status_code'], 204)

    def test_http_not_found_preserves_network_success(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/missing', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual([r['success'] for r in rec['results']], [True, True, False])
        self.assertEqual(rec['diagnosis']['code'], 'http_not_found')
        self.assertIn('HTTP status: 404', rec['diagnosis']['evidence'])

    def test_service_unavailable_http_503(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/error', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual(rec['results'][-1]['details']['status_code'], 503)
        self.assertEqual(rec['diagnosis']['code'], 'http_server_error')

    def test_redirect_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/redirect', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual(rec['results'][-1]['details']['status_code'], 302)
        self.assertEqual(rec['diagnosis']['code'], 'http_redirect')

    def test_http_authentication_required(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/auth', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual(rec['diagnosis']['code'], 'http_authentication_required')

    def test_http_forbidden(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/forbidden', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual(rec['diagnosis']['code'], 'http_access_forbidden')

    def test_http_other_client_error(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic('/teapot', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual(rec['diagnosis']['code'], 'http_client_error')

    def test_tcp_only_uses_one_check(self):
        with tempfile.TemporaryDirectory() as temp:
            code, rec = self.run_diagnostic(only='tcp', output=Path(temp) / 'd.jsonl')
        self.assertEqual(code, 0)
        self.assertEqual([r['check'] for r in rec['results']], ['tcp'])

    def test_jsonl_appends_success_and_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'nested' / 'd.jsonl'
            self.run_diagnostic('/', output=path)
            self.run_diagnostic('/missing', output=path)
            records = [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(records), 2)
        self.assertEqual([r['overall_success'] for r in records], [True, False])
        self.assertEqual(records[1]['diagnosis']['code'], 'http_not_found')

    def test_dns_failure_does_not_skip_independent_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'diag.jsonl'
            dns_failed = CheckResult('dns', '127.0.0.1', False, 1, error='gaierror')
            with patch('cli.resolve_host', return_value=dns_failed) as dns:
                code, rec = self.run_diagnostic(output=report)
                dns.assert_called_once()
        self.assertEqual(code, 1)
        self.assertEqual([r['success'] for r in rec['results']], [False, True, True])
        self.assertEqual(rec['diagnosis']['code'], 'mixed_results')

    def test_invalid_target_does_not_call_probes_or_write_report(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'diag.jsonl'
            with (
                patch('cli.resolve_host') as dns,
                patch('cli.connect_tcp') as tcp,
                patch('cli.check_http') as http,
                redirect_stderr(StringIO()),
            ):
                with self.assertRaises(SystemExit) as exc:
                    cli.main(['--port', '65536', '--output', str(report)])
                dns.assert_not_called()
                tcp.assert_not_called()
                http.assert_not_called()
        self.assertEqual(exc.exception.code, 2)
        self.assertFalse(report.exists())


if __name__ == '__main__':
    unittest.main()
