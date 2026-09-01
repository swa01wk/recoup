"""
AgentCore runtime adapter.

Handles communication with the Amazon Bedrock AgentCore Runtime:
  - Invoking the Recoup agent via the AgentCore Runtime endpoint
  - Processing streamed events from the runtime
  - Registering tools with the AgentCore Gateway

Phase 1: The invoke method is stubbed. Phase 2 wires real boto3
bedrock-agent-runtime calls.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3

from ..config import settings

log = logging.getLogger(__name__)


class AgentCoreAdapter:
    """
    Thin wrapper around Amazon Bedrock AgentCore Runtime.

    Provides a ``invoke`` method that submits a prompt to the AgentCore
    Runtime and returns streamed response chunks.
    """

    def __init__(self) -> None:
        self._region = settings.bedrock_region
        self._runtime_arn = settings.agentcore_runtime_arn
        self._gateway_url = settings.agentcore_gateway_url

    def invoke(
        self,
        prompt: str,
        session_id: str,
        memory_id: str | None = None,
        extra_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Invoke the Recoup agent on AgentCore Runtime.

        Args:
            prompt: User prompt or system trigger payload (JSON string).
            session_id: Unique session identifier for HITL continuity.
            memory_id: Optional AgentCore Memory store ID.
            extra_context: Additional context injected into the session.

        Returns:
            Parsed agent response dict.
        """
        if not self._runtime_arn:
            log.warning("agentcore.invoke: no runtime ARN configured — returning stub response")
            return {
                "sessionId": session_id,
                "output": {"text": "[AgentCore stub — not configured]"},
                "_stub": True,
            }

        # Phase 2: real invocation
        client = boto3.client("bedrock-agent-runtime", region_name=self._region)
        response = client.invoke_agent(
            agentId=self._runtime_arn.split("/")[-1],
            agentAliasId="TSTALIASID",
            sessionId=session_id,
            inputText=prompt,
        )

        completion = ""
        for event in response.get("completion", []):
            chunk = event.get("chunk", {})
            completion += chunk.get("bytes", b"").decode("utf-8", errors="replace")

        return {"sessionId": session_id, "output": {"text": completion}}

    def register_tool(
        self,
        tool_name: str,
        lambda_arn: str,
        input_schema: dict[str, Any],
        description: str,
        action_class: str = "READ",
    ) -> dict[str, Any]:
        """
        Register a tool with the AgentCore Gateway.

        This is called by the deployment script, not at runtime.

        Args:
            tool_name: Tool identifier (must match TOOL_REGISTRY key).
            lambda_arn: Lambda function ARN to invoke when the tool is called.
            input_schema: JSON Schema for the tool's input parameters.
            description: Human-readable description for the agent.
            action_class: Authorization class (READ, WRITE_INTERNAL, etc.).

        Returns:
            Gateway registration response.
        """
        log.info("agentcore.register_tool tool=%s action_class=%s", tool_name, action_class)
        # Phase 2: call AgentCore Gateway API
        return {
            "tool_name": tool_name,
            "registered": True,
            "_stub": True,
        }

    def register_all_tools(self) -> list[dict[str, Any]]:
        """Register all tools from TOOL_REGISTRY with the AgentCore Gateway."""
        import inspect

        from ..tools.registry import TOOL_REGISTRY

        results = []
        for meta in TOOL_REGISTRY.values():
            sig = inspect.signature(meta.fn)
            schema = {
                "type": "object",
                "properties": {
                    name: {"type": "string", "description": str(param.annotation)}
                    for name, param in sig.parameters.items()
                },
            }
            result = self.register_tool(
                tool_name=meta.name,
                lambda_arn=f"arn:aws:lambda:{self._region}:*:function:{meta.lambda_target}",
                input_schema=schema,
                description=meta.description,
                action_class=meta.action_class,
            )
            results.append(result)
        return results
