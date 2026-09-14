"""Allow-listed remediation actions per AWS service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemediationCatalogEntry:
    action_id: str
    label: str
    reversibility: str
    destructive: bool = False


_CATALOG: dict[str, list[RemediationCatalogEntry]] = {
    "EC2": [
        RemediationCatalogEntry("stop", "Stop EC2 instance", "reversible", False),
        RemediationCatalogEntry("schedule_stop", "Schedule stop/start", "reversible", False),
        RemediationCatalogEntry("resize", "Right-size instance type", "reversible", False),
        RemediationCatalogEntry("terminate", "Terminate instance", "destructive", True),
        RemediationCatalogEntry("investigate", "Investigate further", "reversible", False),
        RemediationCatalogEntry("none", "Do nothing", "reversible", False),
    ],
    "RDS": [
        RemediationCatalogEntry("resize", "Resize RDS instance", "reversible", False),
        RemediationCatalogEntry("storage_opt", "Optimize storage", "reversible", False),
        RemediationCatalogEntry("stop", "Stop RDS instance", "reversible", False),
        RemediationCatalogEntry("terminate", "Delete RDS instance", "destructive", True),
        RemediationCatalogEntry("investigate", "Investigate further", "reversible", False),
        RemediationCatalogEntry("none", "Do nothing", "reversible", False),
    ],
    "EBS": [
        RemediationCatalogEntry("snapshot_delete", "Snapshot then delete", "partial", True),
        RemediationCatalogEntry(
            "delete_unattached", "Delete unattached volume", "destructive", True
        ),
        RemediationCatalogEntry("change_type", "Change volume type", "reversible", False),
        RemediationCatalogEntry("retain", "Retain volume", "reversible", False),
        RemediationCatalogEntry("investigate", "Investigate further", "reversible", False),
    ],
}

_DEFAULT = [
    RemediationCatalogEntry("investigate", "Investigate further", "reversible", False),
    RemediationCatalogEntry("none", "Do nothing", "reversible", False),
]


def catalog_for_service(service: str) -> list[RemediationCatalogEntry]:
    key = service.strip().upper()
    if key == "LOAD BALANCER":
        key = "LB"
    return list(_CATALOG.get(key, _DEFAULT))
