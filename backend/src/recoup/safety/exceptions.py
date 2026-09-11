"""
Safety layer exceptions — all safety violations raise a typed error.

Design: every error class carries enough context for structured logging
without embedding raw evidence content (which must never leave the pipeline).
"""

from __future__ import annotations


class SanitizationError(Exception):
    """
    Raised by EvidenceSanitizer when a high-risk pattern survives all redaction
    passes.  Fails closed — the evidence item is quarantined and the run halts.
    """

    def __init__(self, message: str, evidence_id: str) -> None:
        super().__init__(message)
        self.evidence_id = evidence_id

    def __str__(self) -> str:  # noqa: D105
        return f"SanitizationError(evidence_id={self.evidence_id!r}): {self.args[0]}"


class ToolDeniedError(Exception):
    """
    Raised by ``check_autonomy`` when a tool's autonomy class is BLACK (disabled
    in V1) or when policy evaluation returns DENY.

    Not retryable — the operation is structurally prohibited.
    """

    def __init__(self, tool_name: str, reason: str) -> None:
        super().__init__(f"Tool '{tool_name}' denied: {reason}")
        self.tool_name = tool_name
        self.reason = reason


class ApprovalRequiredError(Exception):
    """
    Raised by ``check_autonomy`` when a RED-class tool is invoked without a
    valid (non-expired, non-stale) ApprovalRecord.

    The caller should transition the opportunity to AWAITING_APPROVAL and
    surface the approval card to the human operator.
    """

    def __init__(self, tool_name: str, opportunity_id: str) -> None:
        super().__init__(
            f"Tool '{tool_name}' requires human approval for opportunity '{opportunity_id}'"
        )
        self.tool_name = tool_name
        self.opportunity_id = opportunity_id
