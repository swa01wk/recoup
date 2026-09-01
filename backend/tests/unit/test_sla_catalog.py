"""
Unit tests for the SLA catalog.

Validates that every contract in the catalog:
  1. Loads correctly as a SLAContract
  2. Has a source_hash starting with 'sha256:'
  3. Has a non-empty source_url
  4. Has at least one credit tier
  5. Has at least one required claim field
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from recoup.models.sla import SLAContract

_CATALOG_DIR = Path(__file__).parent.parent.parent.parent / "sla_catalog"


def _all_contract_paths() -> list[Path]:
    paths = []
    for service_dir in sorted(_CATALOG_DIR.iterdir()):
        if service_dir.is_dir():
            paths.extend(sorted(service_dir.glob("*.yaml")))
    return paths


class TestSLACatalog:
    def test_catalog_directory_exists(self) -> None:
        assert _CATALOG_DIR.exists(), f"sla_catalog directory not found at {_CATALOG_DIR}"

    def test_at_least_one_contract(self) -> None:
        paths = _all_contract_paths()
        assert len(paths) >= 1, "Expected at least one SLA contract in the catalog"

    @pytest.mark.parametrize("contract_path", _all_contract_paths())
    def test_contract_loads_without_error(self, contract_path: Path) -> None:
        with contract_path.open() as f:
            data = yaml.safe_load(f)
        contract = SLAContract(**data)
        assert contract.service, f"{contract_path}: service must be non-empty"

    @pytest.mark.parametrize("contract_path", _all_contract_paths())
    def test_contract_has_source_hash(self, contract_path: Path) -> None:
        with contract_path.open() as f:
            data = yaml.safe_load(f)
        contract = SLAContract(**data)
        assert contract.source_hash.startswith("sha256:"), (
            f"{contract_path}: source_hash must start with 'sha256:'. "
            f"Got: {contract.source_hash!r}. "
            "Run the CI hash-update script to populate it."
        )

    @pytest.mark.parametrize("contract_path", _all_contract_paths())
    def test_contract_has_source_url(self, contract_path: Path) -> None:
        with contract_path.open() as f:
            data = yaml.safe_load(f)
        contract = SLAContract(**data)
        assert contract.source_url, f"{contract_path}: source_url must not be empty"

    @pytest.mark.parametrize("contract_path", _all_contract_paths())
    def test_contract_has_credit_tiers(self, contract_path: Path) -> None:
        with contract_path.open() as f:
            data = yaml.safe_load(f)
        contract = SLAContract(**data)
        assert len(contract.credit_tiers) >= 1, (
            f"{contract_path}: contract must have at least one credit tier"
        )

    @pytest.mark.parametrize("contract_path", _all_contract_paths())
    def test_contract_has_required_claim_fields(self, contract_path: Path) -> None:
        with contract_path.open() as f:
            data = yaml.safe_load(f)
        contract = SLAContract(**data)
        assert len(contract.required_claim_fields) >= 1, (
            f"{contract_path}: contract must have at least one required_claim_field"
        )

    def test_apigateway_2022_resolves_correct_tier(self) -> None:
        """Smoke test: API Gateway contract resolves 10% tier for 99.9306% uptime."""
        path = _CATALOG_DIR / "api_gateway" / "2022-05-05.yaml"
        assert path.exists(), f"Canonical contract not found at {path}"
        with path.open() as f:
            data = yaml.safe_load(f)
        from decimal import Decimal
        contract = SLAContract(**data)
        tier = contract.resolve_tier(Decimal("99.9306"))
        assert tier == Decimal("10"), f"Expected 10% tier, got {tier}"
