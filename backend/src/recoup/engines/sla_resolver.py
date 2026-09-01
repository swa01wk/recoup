"""
SLA contract resolver — loads the correct contract version from the local catalog.

Never fetches from the web at claim time. Contracts must be in the catalog
with source_hash populated. A CI test enforces this invariant.
"""

from datetime import date
from pathlib import Path

import yaml

from ..models.sla import SLAContract

_CATALOG_DIR = Path(__file__).parent.parent.parent.parent.parent / "sla_catalog"


class SLAContractNotFoundError(Exception):
    pass


def resolve_sla_contract(service: str, region: str, incident_date: date) -> SLAContract:
    """
    Return the SLA contract effective on the given incident date.

    Args:
        service: AWS service identifier (e.g. 'apigateway').
        region: AWS region (reserved for future region-specific contracts).
        incident_date: Date of the incident; used to select the correct version.

    Raises:
        SLAContractNotFoundError: If no contract covers the given date.
    """
    contracts = _load_contracts_for_service(service)
    applicable = [
        c
        for c in contracts
        if c.effective_from <= incident_date
        and (c.effective_to is None or c.effective_to >= incident_date)
    ]
    if not applicable:
        raise SLAContractNotFoundError(
            f"No SLA contract found for service='{service}' on date={incident_date}. "
            f"Available versions: {[c.version for c in contracts]}"
        )
    return max(applicable, key=lambda c: c.effective_from)


def _load_contracts_for_service(service: str) -> list[SLAContract]:
    service_dir = _CATALOG_DIR / service
    if not service_dir.exists():
        raise SLAContractNotFoundError(f"No SLA catalog directory for service '{service}'")

    contracts = []
    for yaml_file in sorted(service_dir.glob("*.yaml")):
        with yaml_file.open() as f:
            data = yaml.safe_load(f)
        contracts.append(SLAContract(**data))
    return contracts
