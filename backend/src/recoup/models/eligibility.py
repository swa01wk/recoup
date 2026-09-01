"""Eligibility assessment — produced by the eligibility reasoner agent node."""

from pydantic import BaseModel, Field, model_validator


class EligibilityAssessment(BaseModel):
    eligible_estimate: bool
    confidence: float = Field(ge=0.0, le=1.0)
    satisfied_requirements: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    possible_exclusions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(
        description="Must only contain IDs present in the EvidenceManifest"
    )

    @model_validator(mode="after")
    def low_confidence_has_unresolved(self) -> "EligibilityAssessment":
        if self.confidence < 0.7 and not self.unresolved and not self.possible_exclusions:
            raise ValueError(
                "Low-confidence assessment must list unresolved items or possible exclusions"
            )
        return self
