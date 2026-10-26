"""Unit tests for DNS and TCP diagnostics (no external network access)."""
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dns_check import resolve_host
from tcp_check import connect_tcp


class DnsTests(unittest.TestCase):
    @patch("dns_check.socket.getaddrinfo")
    def test_dns_deduplicates_and_sorts_addresses(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 0)),
        ]
        result = resolve_host("example.test")
        self.assertTrue(result.success)
        self.assertEqual(result.details["addresses"], ["10.0.0.1", "10.0.0.2"])
        self.assertEqual(result.details["address_count"], 2)

    @patch("dns_check.socket.getaddrinfo", side_effect=socket.gaierror("Name not found"))
    def test_dns_failure_is_reported(self, _):
        result = resolve_host("missing.test")
        self.assertFalse(result.success)
        self.assertIn("gaierror", result.error)

    @patch("dns_check.socket.getaddrinfo", return_value=[])
    def test_dns_no_answers(self, _):
        result = resolve_host("empty.test")
        self.assertFalse(result.success)
        self.assertEqual(result.details["address_count"], 0)


class TcpTests(unittest.TestCase):
    @patch("tcp_check.socket.create_connection")
    def test_tcp_connection_success(self, create_connection):
        result = connect_tcp("127.0.0.1", 18765, 2.0)
        self.assertTrue(result.success)
        create_connection.assert_called_once_with(("127.0.0.1", 18765), timeout=2.0)
        create_connection.return_value.__enter__.assert_called_once()
        create_connection.return_value.__exit__.assert_called_once()

    @patch("tcp_check.socket.create_connection", side_effect=ConnectionRefusedError("refused"))
    def test_tcp_refused(self, _):
        result = connect_tcp("127.0.0.1", 18765, 2.0)
        self.assertFalse(result.success)
        self.assertIn("ConnectionRefusedError", result.error)

    @patch("tcp_check.socket.create_connection", side_effect=TimeoutError("timed out"))
    def test_tcp_timeout(self, _):
        result = connect_tcp("127.0.0.1", 18765, 1.0)
        self.assertFalse(result.success)
        self.assertIn("TimeoutError", result.error)
