"""Shared result structure for individual diagnostic checks."""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    check: str
    target: str
    success: bool
    latency_ms: float
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
