"""Test one explicitly supplied TCP host/port; not a port scanner."""
import socket
from time import perf_counter

from models import CheckResult


def connect_tcp(host: str, port: int, timeout: float) -> CheckResult:
    start = perf_counter()
    target = f"{host}:{port}"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return CheckResult(
            check="tcp",
            target=target,
            success=True,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            details={"port": port, "connected": True},
        )
    except OSError as exc:
        return CheckResult(
            check="tcp",
            target=target,
            success=False,
            latency_ms=round((perf_counter() - start) * 1000, 2),
            details={"port": port, "connected": False},
            error=f"{type(exc).__name__}: {exc}",
        )
