// ============================================================================
// Recoup AgentCore Cedar Policies
// Version: 1.0.0  |  Phase 3
//
// Policy model:
//   principal: RecoupRuntime (the Strands agent execution identity)
//   action:    Tool calls (action strings match TOOL_REGISTRY keys)
//   resource:  RecoupGateway (the AgentCore Tool Gateway endpoint)
//
// Evaluation order:
//   1. Forbid rules  — hard deny; cannot be overridden by any permit
//   2. Permit rules  — specific preconditions per action
//   3. Default deny  — Cedar's implicit default; no matching permit → DENY
// ============================================================================

// ----------------------------------------------------------------------------
// PERMIT — Read-only tools (GREEN autonomy class)
// Always permitted for authenticated Recoup runtime sessions.
// ----------------------------------------------------------------------------
permit(
  principal is RecoupRuntime,
  action in [
    Action::"get_cloudwatch_metrics",
    Action::"query_cloudwatch_logs",
    Action::"get_health_event",
    Action::"get_cost_and_usage",
    Action::"get_cost_anomalies",
    Action::"list_cost_optimization_recommendations",
    Action::"lookup_cloudtrail_events",
    Action::"get_support_case_status"
  ],
  resource is RecoupGateway
) when {
  context.session_authenticated == true
};

// ----------------------------------------------------------------------------
// PERMIT — Internal write tools (YELLOW autonomy class)
// Permitted without human approval; produces audit trail.
// ----------------------------------------------------------------------------
permit(
  principal is RecoupRuntime,
  action in [
    Action::"store_evidence",
    Action::"create_approval_request",
    Action::"simulate_support_case"
  ],
  resource is RecoupGateway
) when {
  context.session_authenticated == true
};

// ----------------------------------------------------------------------------
// PERMIT — submit_support_case (RED autonomy class)
// All 5 preconditions must be satisfied simultaneously:
//   1. simulation_mode must be explicitly disabled (operator opt-in)
//   2. Human has explicitly approved (approval_state == "APPROVED")
//   3. Approval amount exactly matches current claim amount (no tampering)
//   4. Approval has not expired (24h window)
//   5. State version matches approved version (no stale approval reuse)
//   6. Real submission feature flag must be enabled (belt-and-suspenders)
// ----------------------------------------------------------------------------
permit(
  principal is RecoupRuntime,
  action == Action::"submit_support_case",
  resource is RecoupGateway
) when {
  context.simulation_mode == false &&
  context.approval_state == "APPROVED" &&
  context.approval_amount == context.claim_amount &&
  context.approval_expires_at > context.current_time &&
  context.opportunity_state_version == context.approved_state_version &&
  context.recoup_enable_real_submission == true
};

// ----------------------------------------------------------------------------
// PERMIT — stop_demo_instance (RED autonomy class, Phase 6)
// Requires approval + strict allowlist guard:
//   1. simulation_mode must be disabled
//   2. Human approval present and not expired
//   3. Instance must carry the RecoupDemo=true tag
//   4. Account ID must match the allowlisted demo account
// ----------------------------------------------------------------------------
permit(
  principal is RecoupRuntime,
  action == Action::"stop_demo_instance",
  resource is RecoupGateway
) when {
  context.simulation_mode == false &&
  context.approval_state == "APPROVED" &&
  context.target_instance_tag == "RecoupDemo=true" &&
  context.target_account_id == context.allowlisted_demo_account_id &&
  context.approval_expires_at > context.current_time
};

// ----------------------------------------------------------------------------
// FORBID — Destructive infrastructure tools (BLACK autonomy class)
// Hard deny — overrides any permit. Cannot be unlocked in V1.
// ----------------------------------------------------------------------------
forbid(
  principal,
  action in [
    Action::"stop_resource",
    Action::"delete_resource",
    Action::"terminate_ec2_instance"
  ],
  resource
);

// ----------------------------------------------------------------------------
// FORBID — Real support submission in simulation/replay mode
// Prevents the agent from bypassing the simulation_mode check.
// ----------------------------------------------------------------------------
forbid(
  principal,
  action == Action::"submit_support_case",
  resource
) when {
  context.simulation_mode == true
};
