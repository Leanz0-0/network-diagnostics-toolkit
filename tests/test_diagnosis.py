"""Deterministic diagnoses without external network activity."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import cli
from diagnosis import diagnose
from models import CheckResult


def item(name, success, *, status=None, error=None):
    details = {"status_code": status} if status is not None else {}
    return CheckResult(name, "localhost", success, 1.0, details=details, error=error)


class DiagnosisTests(unittest.TestCase):
    def test_rejects_missing_checks(self):
        with self.assertRaises(ValueError):
            diagnose([])

    def test_all_pass(self):
        answer = diagnose([item("dns", True), item("tcp", True), item("http", True)])
        self.assertEqual(answer["code"], "checks_passed")
        self.assertEqual(answer["layer"], "none")

    def test_dns_only_pass(self):
        self.assertEqual(diagnose([item("dns", True)])["code"], "checks_passed")

    def test_dns_resolution_failure(self):
        self.assertEqual(diagnose([item("dns", False, error="gaierror")])["code"], "dns_resolution_failed")

    def test_dns_failure_precedes_other_failures(self):
        answer = diagnose([item("dns", False), item("tcp", False), item("http", False)])
        self.assertEqual(answer["layer"], "dns")

    def test_tcp_refused(self):
        answer = diagnose([item("dns", True), item("tcp", False, error="ConnectionRefusedError: refused"), item("http", False)])
        self.assertEqual(answer["code"], "tcp_connection_refused")

    def test_windows_tcp_refused(self):
        self.assertEqual(diagnose([item("tcp", False, error="OSError: [WinError 10061]")])["code"], "tcp_connection_refused")

    def test_tcp_timeout(self):
        answer = diagnose([item("tcp", False, error="TimeoutError: timed out")])
        self.assertEqual(answer["code"], "tcp_connection_timeout")

    def test_tcp_generic_failure(self):
        self.assertEqual(diagnose([item("tcp", False, error="OSError: unreachable")])["code"], "tcp_connection_failed")

    def test_http_404(self):
        answer = diagnose([item("dns", True), item("tcp", True), item("http", False, status=404)])
        self.assertEqual(answer["code"], "http_not_found")
        self.assertIn("HTTP status: 404", answer["evidence"])

    def test_http_401(self):
        self.assertEqual(diagnose([item("http", False, status=401)])["code"], "http_authentication_required")

    def test_http_403(self):
        self.assertEqual(diagnose([item("http", False, status=403)])["code"], "http_access_forbidden")

    def test_http_302(self):
        self.assertEqual(diagnose([item("http", False, status=302)])["code"], "http_redirect")

    def test_http_418(self):
        self.assertEqual(diagnose([item("http", False, status=418)])["code"], "http_client_error")

    def test_http_503(self):
        self.assertEqual(diagnose([item("http", False, status=503)])["code"], "http_server_error")

    def test_http_transport_failure(self):
        self.assertEqual(diagnose([item("http", False, error="SSLError")])["code"], "http_transport_failed")

    def test_independent_results_disagree(self):
        answer = diagnose([item("dns", False), item("tcp", True), item("http", False)])
        self.assertEqual(answer["code"], "mixed_results")

    def test_tcp_and_http_disagree(self):
        answer = diagnose([item("tcp", False), item("http", True)])
        self.assertEqual(answer["code"], "mixed_results")

    @patch("cli.resolve_host", return_value=item("dns", False, error="gaierror"))
    def test_cli_persists_dns_diagnosis_and_exit_code(self, _):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.jsonl"
            output = StringIO()
            with redirect_stdout(output):
                code = cli.main(["--only", "dns", "--output", str(path)])
            self.assertEqual(code, 1)
            self.assertIn("DIAGNOSIS [dns_resolution_failed]", output.getvalue())
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["diagnosis"]["code"], "dns_resolution_failed")
            self.assertIn("next_step", record["diagnosis"])

    @patch("cli.resolve_host", return_value=item("dns", True))
    def test_cli_persists_healthy_diagnosis(self, _):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.jsonl"
            with redirect_stdout(StringIO()):
                code = cli.main(["--only", "dns", "--output", str(path)])
            self.assertEqual(code, 0)
            record = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(record["diagnosis"]["code"], "checks_passed")


if __name__ == "__main__":
    unittest.main()
