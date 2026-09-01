"""Claim package — assembled by the claim_package_generator agent node."""

from pydantic import BaseModel, Field, model_validator

from .evidence import EvidenceManifest


class ClaimPackage(BaseModel):
    opportunity_id: str
    subject: str
    body: str
    region: str
    billing_cycle: str = Field(description="e.g. '2026-08'")
    resources: list[str]
    evidence_manifest: EvidenceManifest
    calculator_result_hash: str = Field(description="SHA-256 of AvailabilityResult JSON")

    @model_validator(mode="after")
    def evidence_refs_exist_in_manifest(self) -> "ClaimPackage":
        """All evidence IDs in the body must be present in the manifest."""
        manifest_ids = self.evidence_manifest.item_ids
        for ref in self._extract_evidence_refs():
            if ref not in manifest_ids:
                raise ValueError(
                    f"Claim body references unknown evidence id '{ref}' not in manifest. "
                    "LLM must not invent evidence references."
                )
        return self

    def _extract_evidence_refs(self) -> list[str]:
        """Extract ev-* references from claim body."""
        import re
        return re.findall(r"\bev-[a-f0-9]{8}\b", self.body)
