"""Tool audit record — written by AfterToolCall hook for every tool invocation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ToolAudit(BaseModel):
    trace_id: str
    opportunity_id: str
    node: str
    tool: str
    request_hash: str = ""
    response_hash: str = ""
    policy_decision: Literal["ALLOW", "REQUIRE_APPROVAL", "DENY"] = "ALLOW"
    latency_ms: int = 0
    timestamp: datetime
