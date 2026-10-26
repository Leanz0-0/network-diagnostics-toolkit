"""Validation, exit-code, and persistent-report tests."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cli
from models import CheckResult
from reporting import append_report


class InputValidationTests(unittest.TestCase):
    def test_default_url_is_http(self):
        self.assertEqual(
            cli.validate_target("127.0.0.1", 18765, 3, None),
            "http://127.0.0.1:18765/",
        )

    def test_default_port_443_uses_https(self):
        self.assertEqual(
            cli.validate_target("example.test", 443, 3, None),
            "https://example.test:443/",
        )

    def test_ipv6_url_bracketed(self):
        self.assertEqual(
            cli.validate_target("::1", 18765, 3, None),
            "http://[::1]:18765/",
        )

    def test_invalid_port(self):
        with self.assertRaisesRegex(ValueError, "Port"):
            cli.validate_target("localhost", 65536, 2, None)

    def test_invalid_timeout(self):
        with self.assertRaisesRegex(ValueError, "Timeout"):
            cli.validate_target("localhost", 18765, 0, None)

    def test_reject_embedded_credentials(self):
        with self.assertRaisesRegex(ValueError, "credentials"):
            cli.validate_target("localhost", 80, 2, "http://u:p@localhost/")

    def test_reject_query_string(self):
        with self.assertRaisesRegex(ValueError, "queries"):
            cli.validate_target("localhost", 80, 2, "http://localhost/?token=secret")

    def test_reject_mismatched_url_host(self):
        with self.assertRaisesRegex(ValueError, "hostname"):
            cli.validate_target("localhost", 80, 2, "http://example.test/")

    def test_reject_mismatched_url_port(self):
        with self.assertRaisesRegex(ValueError, "port"):
            cli.validate_target("localhost", 8765, 2, "http://localhost:80/")


class ReportingTests(unittest.TestCase):
    def test_jsonl_appends_separate_valid_records(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "reports" / "diagnostics.jsonl"
            append_report({"trial": 1}, target)
            append_report({"trial": 2}, target)
            entries = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual(entries, [{"trial": 1}, {"trial": 2}])

    @patch("cli.resolve_host")
    def test_cli_success_persists_report(self, mock_dns):
        mock_dns.return_value = CheckResult("dns", "127.0.0.1", True, 0.1)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "report.jsonl"
            with redirect_stdout(io.StringIO()):
                code = cli.main(["--only", "dns", "--output", str(output)])
            self.assertEqual(code, 0)
            record = json.loads(output.read_text(encoding="utf-8").strip())
            self.assertTrue(record["overall_success"])
            self.assertEqual(len(record["results"]), 1)
            self.assertIn("timestamp_utc", record)

    @patch("cli.resolve_host")
    def test_cli_failed_network_check_returns_one_and_saves(self, mock_dns):
        mock_dns.return_value = CheckResult("dns", "127.0.0.1", False, 1.0, error="simulated")
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "report.jsonl"
            with redirect_stdout(io.StringIO()):
                code = cli.main(["--only", "dns", "--output", str(output)])
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(output.read_text())["overall_success"])

    def test_invalid_input_exits_two(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            cli.main(["--port", "70000"])
        self.assertEqual(error.exception.code, 2)

    @patch("cli.resolve_host")
    def test_report_failure_returns_three(self, mock_dns):
        mock_dns.return_value = CheckResult("dns", "127.0.0.1", True, 1.0)
        with tempfile.TemporaryDirectory() as temp:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = cli.main(["--only", "dns", "--output", temp])
            self.assertEqual(code, 3)
