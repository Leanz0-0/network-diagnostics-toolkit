"""Issue one HTTP GET and inspect its response; redirects are not followed."""
import http.client
from time import perf_counter
from urllib.parse import urlsplit

from models import CheckResult


def check_http(url: str, timeout: float) -> CheckResult:
    start = perf_counter()
    parsed = urlsplit(url)
    conn = None
    try:
        host = parsed.hostname
        if not host or parsed.scheme not in {"http", "https"}:
            raise ValueError("A valid HTTP or HTTPS URL is required")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        conn_class = (
            http.client.HTTPSConnection
            if parsed.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = conn_class(host, port, timeout=timeout)
        conn.request(
            "GET", parsed.path or "/",
            headers={"User-Agent": "NetworkDiagnosticsToolkit/0.1"},
        )
        response = conn.getresponse()
        status = response.status
        return CheckResult(
            check="http",
            target=url,
            success=200 <= status < 300,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            details={"status_code": status, "reason": response.reason},
            error=None if 200 <= status < 300 else f"HTTP {status}",
        )
    except (OSError, ValueError, http.client.HTTPException) as exc:
        return CheckResult(
            check="http",
            target=url,
            success=False,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        if conn is not None:
            conn.close()
