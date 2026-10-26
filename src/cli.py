"""Command-line orchestration and input validation."""
import argparse
from datetime import datetime, timezone
import ipaddress
import re
import sys
from urllib.parse import urlsplit

from dns_check import resolve_host
from http_check import check_http
from reporting import append_report
from tcp_check import connect_tcp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Diagnose DNS, a single TCP port, and an HTTP endpoint."
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host or IP to check")
    parser.add_argument("--port", type=int, default=18765, help="Single TCP port")
    parser.add_argument("--url", help="HTTP URL (must match --host and --port)")
    parser.add_argument("--timeout", type=float, default=3.0, help="Seconds (0–30]")
    parser.add_argument(
        "--only", choices=("all", "dns", "tcp", "http"), default="all",
        help="Which check to execute (default: all)",
    )
    parser.add_argument(
        "--output", default="reports/diagnostics.jsonl",
        help="JSONL output file",
    )
    return parser


def validate_target(host: str, port: int, timeout: float, url: str | None) -> str:
    if not host or host != host.strip() or len(host) > 253:
        raise ValueError("Host must be a nonempty name or address without whitespace")
    if ":" in host:
        try:
            ipaddress.IPv6Address(host)
        except ValueError as exc:
            raise ValueError("A colon is permitted only in a valid IPv6 address") from exc
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", host):
        raise ValueError("Host contains unsupported characters")
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535")
    if not 0 < timeout <= 30:
        raise ValueError("Timeout must be greater than 0 and at most 30 seconds")

    if url is None:
        scheme = "https" if port == 443 else "http"
        uri_host = f"[{host}]" if ":" in host else host
        return f"{scheme}://{uri_host}:{port}/"

    if any(character.isspace() for character in url):
        raise ValueError("URL cannot contain whitespace")
    try:
        parsed = urlsplit(url)
        effective_port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError("URL contains an invalid port or host") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be HTTP or HTTPS and include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Embedded URL credentials are not allowed")
    if parsed.query or parsed.fragment:
        raise ValueError("URL queries and fragments are not allowed in saved reports")
    if parsed.hostname.rstrip(".").lower() != host.rstrip(".").lower():
        raise ValueError("URL hostname must match --host")
    if effective_port != port:
        raise ValueError("URL port must match --port")
    return url


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        url = validate_target(args.host, args.port, args.timeout, args.url)
    except ValueError as exc:
        parser.error(str(exc))  # argparse exits with code 2.

    results = []
    if args.only in ("all", "dns"):
        results.append(resolve_host(args.host))
    if args.only in ("all", "tcp"):
        results.append(connect_tcp(args.host, args.port, args.timeout))
    if args.only in ("all", "http"):
        results.append(check_http(url, args.timeout))

    healthy = all(result.success for result in results)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": args.host,
        "port": args.port,
        "url": url,
        "overall_success": healthy,
        "results": [result.to_dict() for result in results],
    }

    print("=== Network Diagnostics Toolkit ===")
    for result in results:
        state = "PASS" if result.success else "FAIL"
        print(f"[{state}] {result.check.upper():4} {result.target} ({result.latency_ms:.2f} ms)")
        if result.details:
            print(f"       {result.details}")
        if result.error:
            print(f"       {result.error}")

    try:
        destination = append_report(report, args.output)
    except OSError as exc:
        print(f"ERROR: Could not save diagnostic report: {exc}", file=sys.stderr)
        return 3

    print(f"Report saved: {destination}")
    return 0 if healthy else 1
