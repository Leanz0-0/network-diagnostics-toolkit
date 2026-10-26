"""Loopback-only integration tests using an ephemeral HTTP server."""
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cli import main
from dns_check import resolve_host
from http_check import check_http
from tcp_check import connect_tcp


class TestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/ok":
            status = 200
        elif self.path == "/redirect":
            status = 302
        else:
            status = 404
        self.send_response(status)
        if status == 302:
            self.send_header("Location", "https://example.invalid/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *_args):
        pass


class LocalIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TestHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def test_loopback_dns(self):
        self.assertTrue(resolve_host("127.0.0.1").success)

    def test_loopback_tcp_open(self):
        self.assertTrue(connect_tcp("127.0.0.1", self.port, 2).success)

    def test_http_200(self):
        result = check_http(f"http://127.0.0.1:{self.port}/ok", 2)
        self.assertTrue(result.success)
        self.assertEqual(result.details["status_code"], 200)

    def test_http_404_is_not_network_exception(self):
        result = check_http(f"http://127.0.0.1:{self.port}/missing", 2)
        self.assertFalse(result.success)
        self.assertEqual(result.details["status_code"], 404)
        self.assertEqual(result.error, "HTTP 404")

    def test_redirect_is_not_followed(self):
        result = check_http(f"http://127.0.0.1:{self.port}/redirect", 2)
        self.assertFalse(result.success)
        self.assertEqual(result.details["status_code"], 302)

    def test_full_cli_generates_report(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "reports" / "report.jsonl"
            with redirect_stdout(io.StringIO()):
                code = main([
                    "--host", "127.0.0.1", "--port", str(self.port),
                    "--url", f"http://127.0.0.1:{self.port}/ok",
                    "--output", str(path),
                ])
            self.assertEqual(code, 0)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual([r["check"] for r in record["results"]], ["dns", "tcp", "http"])
            self.assertTrue(record["overall_success"])
