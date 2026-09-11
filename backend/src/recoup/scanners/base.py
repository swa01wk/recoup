"""Base class for all account scanners."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import structlog

from .finding import Finding

if TYPE_CHECKING:
    pass

log: structlog.BoundLogger = structlog.get_logger(__name__)


class BaseScanner(ABC):
    """
    Abstract base for per-service scanners.

    Each scanner catches all exceptions internally so a single failing service
    never blocks the full scan. Errors are collected into ``errors`` and the
    scanner returns an empty list.
    """

    @property
    @abstractmethod
    def service_name(self) -> str:
        """Human-readable service name (e.g. 'EC2')."""
        ...

    @abstractmethod
    def _scan(self, session: Any, region: str) -> list[Finding]:
        """Run the actual scan. May raise — caller wraps in try/except."""
        ...

    def scan(self, session: Any, region: str) -> tuple[list[Finding], list[str]]:
        """
        Run the scanner and return (findings, errors).

        Never raises — all exceptions are caught and returned as error strings.
        """
        try:
            findings = self._scan(session, region)
            log.info(
                "scanner.complete",
                service=self.service_name,
                region=region,
                findings=len(findings),
            )
            return findings, []
        except Exception as exc:  # noqa: BLE001
            msg = f"{self.service_name}: {exc}"
            log.warning("scanner.failed", service=self.service_name, region=region, error=str(exc))
            return [], [msg]
