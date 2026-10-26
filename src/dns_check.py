"""Resolve a hostname via the operating system's DNS resolver."""
import socket
from time import perf_counter

from models import CheckResult


def resolve_host(host: str) -> CheckResult:
    start = perf_counter()
    try:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses = sorted({record[4][0] for record in records})
        success = bool(addresses)
        return CheckResult(
            check="dns",
            target=host,
            success=success,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            details={"addresses": addresses, "address_count": len(addresses)},
            error=None if success else "Resolver returned no addresses",
        )
    except OSError as exc:
        return CheckResult(
            check="dns",
            target=host,
            success=False,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            error=f"{type(exc).__name__}: {exc}",
        )
