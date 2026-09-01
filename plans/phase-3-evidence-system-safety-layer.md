# Phase 3 — Evidence System, Safety Layer & HITL Approval

**Timeline:** Day 7–10 (Target: by Sep 10, 2026)  
**Status:** `[ ] Not Started`  
**Depends on:** Phase 1 complete; Phase 2 can run in parallel

---

## Objective

Build the complete evidence pipeline (collection → sanitization → storage → manifest), the safety and trust layer (deterministic redaction, AgentCore Policy Cedar rules, autonomy class enforcement), and the Human-in-the-Loop (HITL) approval flow. This phase makes Recoup trustworthy — every external financial action requires human approval and policy authorization.

---

## Goals

- [ ] Evidence collector stores raw evidence to S3 with SHA-256 hash
- [ ] Evidence sanitizer applies deterministic redaction (regex + structured field rules)
- [ ] Sanitizer fails closed when high-risk pattern remains after redaction
- [ ] Raw evidence never enters the LLM context or user-visible trace
- [ ] Cedar policies enforce: READ tools → automatic; WRITE_EXTERNAL_FINANCIAL → approval + policy
- [ ] AgentCore Policy `submit_support_case` rule works correctly (all 5 preconditions)
- [ ] Approval records are bound to claim hash + amount + state version + expiry
- [ ] Approval expiry works; expired approvals are rejected by policy
- [ ] Decision Inbox API returns pending approvals; approve/decline endpoints work
- [ ] Approval flow tested with all policy/HITL scenario tests

---

## Workstreams

### 3.1 Evidence Collection

**Location:** `backend/src/recoup/evidence/collector.py`

```python
class EvidenceCollector:
    """
    Collects evidence required by the SLA contract.
    Stores raw evidence to S3; never passes raw content to LLM.
    """

    async def collect(
        self,
        contract: SLAContract,
        signal: IncidentSignal,
        opportunity_id: str,
    ) -> EvidenceManifest:
        items = []
        missing = []

        for field in contract.required_claim_fields:
            try:
                item = await self._collect_field(field, signal, opportunity_id)
                items.append(item)
            except EvidenceNotFoundError:
                missing.append(field)

        return EvidenceManifest(
            opportunity_id=opportunity_id,
            items=items,
            missing_fields=missing,
            redaction_report=RedactionReport(),  # populated by sanitizer
        )

    async def _collect_field(
        self, field: str, signal: IncidentSignal, opportunity_id: str
    ) -> EvidenceItem:
        raw_content = await self._fetch_raw(field, signal)
        
        # Store raw evidence to S3 — never expose this to LLM
        s3_key = f"evidence/raw/{opportunity_id}/{field}/{uuid4()}.json"
        await self.s3.put_object(
            Bucket=EVIDENCE_BUCKET,
            Key=s3_key,
            Body=json.dumps(raw_content),
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=EVIDENCE_KMS_KEY_ID,
        )
        content_hash = sha256(json.dumps(raw_content, sort_keys=True).encode()).hexdigest()

        return EvidenceItem(
            id=f"ev-{uuid4().hex[:8]}",
            type=FIELD_TO_TYPE[field],
            source=field,
            timestamp_range=(signal.start, signal.end),
            storage_uri=f"s3://{EVIDENCE_BUCKET}/{s3_key}",
            sanitized_uri=None,  # populated by sanitizer
            hash=f"sha256:{content_hash}",
            sensitivity=FIELD_SENSITIVITY[field],
            status="FOUND",
        )
```

### 3.2 Evidence Sanitizer

**Location:** `backend/src/recoup/evidence/sanitizer.py`

This is a deterministic stage — no LLM involved. Fail-closed design.

```python
# Redaction patterns — compiled at module load
REDACTION_PATTERNS = [
    # Authorization headers
    (re.compile(r'(?i)(authorization:\s*)(bearer\s+[\w\-\.]+)', re.MULTILINE),
     r'\1[REDACTED-AUTH-TOKEN]'),
    # API keys in query strings / JSON
    (re.compile(r'(?i)(api[_-]?key["\s]*[:=]\s*["\']?)([^"\'&\s,}]{8,})', re.MULTILINE),
     r'\1[REDACTED-API-KEY]'),
    # Cookies
    (re.compile(r'(?i)(cookie:\s*)(.+)', re.MULTILINE),
     r'\1[REDACTED-COOKIE]'),
    # JWT tokens
    (re.compile(r'eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}'),
     '[REDACTED-JWT]'),
    # AWS secret access keys
    (re.compile(r'(?<![A-Z0-9])[A-Z0-9]{40}(?![A-Z0-9])'),
     '[REDACTED-AWS-SECRET]'),
    # Generic email-like PII
    (re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'),
     '[REDACTED-EMAIL]'),
]

# Second-pass scanner: known secret patterns that should never survive redaction
HIGH_RISK_SCANNER = re.compile(
    r'(?i)(password|secret|private.?key|credential|token)[\s]*[:=][\s]*[^\s,}]{8,}'
)

class EvidenceSanitizer:

    def sanitize(self, item: EvidenceItem) -> tuple[EvidenceItem, RedactionReport]:
        raw_content = self._load_raw(item.storage_uri)
        sanitized, redaction_count = self._apply_redactions(raw_content)

        # Second-pass scan — fail closed
        if HIGH_RISK_SCANNER.search(sanitized):
            raise SanitizationError(
                message="High-risk pattern detected in sanitized output; failing closed",
                evidence_id=item.id,
            )

        sanitized_key = item.storage_uri.replace("/raw/", "/sanitized/")
        self._store_sanitized(sanitized_key, sanitized)

        raw_hash = sha256(raw_content.encode()).hexdigest()
        sanitized_hash = sha256(sanitized.encode()).hexdigest()

        report = RedactionReport(
            evidence_id=item.id,
            redaction_count=redaction_count,
            raw_hash=f"sha256:{raw_hash}",
            sanitized_hash=f"sha256:{sanitized_hash}",
            patterns_applied=[p.__class__.__name__ for p, _ in REDACTION_PATTERNS],
        )

        return item.copy(update={"sanitized_uri": sanitized_key, "status": "REDACTED"}), report

    def _apply_redactions(self, content: str) -> tuple[str, int]:
        count = 0
        for pattern, replacement in REDACTION_PATTERNS:
            new_content, n = re.subn(pattern, replacement, content)
            count += n
            content = new_content
        return content, count
```

**Sanitization test scenarios (from spec):**
- Authorization header → `[REDACTED-AUTH-TOKEN]`
- Cookie value → `[REDACTED-COOKIE]`
- API key in JSON → `[REDACTED-API-KEY]`
- PII email → `[REDACTED-EMAIL]`
- Nested JSON secret → caught and redacted
- Scanner false positive → does not redact legitimate content

### 3.3 AgentCore Policy (Cedar)

**Location:** `infra/policy/recoup-policy.cedar`

```cedar
// Permit read-only AWS tools for authenticated Recoup runtime sessions
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
    Action::"store_evidence",
    Action::"create_approval_request",
    Action::"simulate_support_case"
  ],
  resource is RecoupGateway
) when {
  context.session_authenticated == true
};

// Permit submit_support_case ONLY with all preconditions satisfied
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

// Permit stop_demo_instance ONLY for the allowlisted demo resource
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

// Forbid ALL destructive infrastructure tools — hard deny in V1
forbid(
  principal,
  action in [
    Action::"stop_resource",
    Action::"delete_resource",
    Action::"terminate_ec2_instance"
  ],
  resource
);

// Forbid replay from calling real Support API
forbid(
  principal,
  action == Action::"submit_support_case",
  resource
) when {
  context.simulation_mode == true
};
```

**Policy integration tests:**
```python
def test_policy_denies_submit_without_approval():
    ctx = build_context(approval_state="PENDING", simulation_mode=False)
    assert evaluate_policy("submit_support_case", ctx) == "DENY"

def test_policy_denies_submit_in_simulation_mode():
    ctx = build_context(approval_state="APPROVED", simulation_mode=True)
    assert evaluate_policy("submit_support_case", ctx) == "DENY"

def test_policy_denies_stale_approval():
    ctx = build_context(
        approval_state="APPROVED",
        approval_expires_at=datetime.utcnow() - timedelta(minutes=1)
    )
    assert evaluate_policy("submit_support_case", ctx) == "DENY"

def test_policy_denies_amount_mismatch():
    ctx = build_context(
        approval_state="APPROVED",
        approval_amount=Decimal("1840"),
        claim_amount=Decimal("1900"),  # regenerated package
    )
    assert evaluate_policy("submit_support_case", ctx) == "DENY"

def test_policy_denies_destructive_tools():
    for action in ["stop_resource", "delete_resource", "terminate_ec2_instance"]:
        assert evaluate_policy(action, ctx) == "DENY"
```

### 3.4 HITL Approval Flow

**Location:** `backend/src/recoup/approval/`

**Approval record lifecycle:**

```
create_approval_request
  → PENDING (expires_at = now + 24h)
  → APPROVED (human clicks "Approve" in Decision Inbox)
  → REVOKED (state version changed after approval)
  → EXPIRED (TTL elapsed)
```

**Approval API:**
```python
@router.get("/api/opportunities/{id}/approval")
async def get_pending_approval(id: str) -> ApprovalRecord | None:
    return await fetch_pending_approval(opportunity_id=id)

@router.post("/api/opportunities/{id}/approve")
async def approve_opportunity(id: str, body: ApproveRequest, principal: str = Depends(get_principal)) -> ApprovalRecord:
    """
    Record human approval. Bound to:
    - The exact claim_hash in the request
    - The exact amount in the request
    - The current state_version
    """
    opportunity = await fetch_opportunity(id)
    assert opportunity.state == OpportunityState.AWAITING_APPROVAL
    assert body.claim_hash == opportunity.active_claim_hash
    assert body.amount == opportunity.potential_value

    approval = ApprovalRecord(
        approval_id=str(uuid4()),
        principal=principal,
        action="submit_support_case",
        amount=body.amount,
        claim_hash=body.claim_hash,
        opportunity_id=id,
        state_version=opportunity.state_version,
        timestamp=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=24),
        state="APPROVED",
    )
    await save_approval(approval)
    await transition_state(id, OpportunityState.APPROVED, current_version=opportunity.state_version)
    return approval

@router.post("/api/opportunities/{id}/decline")
async def decline_opportunity(id: str, principal: str = Depends(get_principal)) -> dict:
    await transition_state(id, OpportunityState.DENIED, ...)
    return {"status": "declined"}
```

**Approval card content (what the human sees):**
```
ACTION: Submit SLA Credit Claim to AWS Support
AMOUNT: $1,840.00 (10% of $18,400.00 billed charges)
SERVICE: Amazon API Gateway — us-east-1
BILLING CYCLE: August 2026
EVIDENCE: 4/4 required fields present; 0 missing
CALCULATION: (8,634 / 8,640) × 100 = 99.9306% → 10% tier
BASIS: SLA Contract 2022-05-05, source hash: sha256:...
EXPIRES: 24 hours from now

⚠️  This action will create a real AWS Support case.
    Real Support submission is currently DISABLED (Verified Replay mode).
    Approving will trigger: simulate_support_case → REPLAY case id.

[Approve]  [Decline]
```

### 3.5 Autonomy Class Enforcement

**Location:** `backend/src/recoup/safety/autonomy.py`

```python
class AutonomyClass(Enum):
    GREEN = "GREEN"    # read/analyze — automatic
    YELLOW = "YELLOW"  # internal write — automatic + visible audit
    RED = "RED"        # external financial — human approval + policy required
    BLACK = "BLACK"    # destructive — disabled in V1; policy deny

TOOL_AUTONOMY_CLASS = {
    "get_cloudwatch_metrics": AutonomyClass.GREEN,
    "query_cloudwatch_logs": AutonomyClass.GREEN,
    "get_health_event": AutonomyClass.GREEN,
    "get_cost_and_usage": AutonomyClass.GREEN,
    "get_cost_anomalies": AutonomyClass.GREEN,
    "list_cost_optimization_recommendations": AutonomyClass.GREEN,
    "lookup_cloudtrail_events": AutonomyClass.GREEN,
    "store_evidence": AutonomyClass.YELLOW,
    "create_approval_request": AutonomyClass.YELLOW,
    "simulate_support_case": AutonomyClass.YELLOW,
    "submit_support_case": AutonomyClass.RED,
    "stop_demo_instance": AutonomyClass.RED,
    "stop_resource": AutonomyClass.BLACK,
    "delete_resource": AutonomyClass.BLACK,
    "terminate_ec2_instance": AutonomyClass.BLACK,
}

def check_autonomy(tool_name: str, context: ToolContext) -> None:
    cls = TOOL_AUTONOMY_CLASS.get(tool_name, AutonomyClass.BLACK)
    if cls == AutonomyClass.BLACK:
        raise ToolDeniedError(f"Tool '{tool_name}' is disabled in V1 (BLACK autonomy class)")
    if cls == AutonomyClass.RED:
        if context.approval_state != "APPROVED":
            raise ApprovalRequiredError(f"Tool '{tool_name}' requires human approval")
```

---

## Definition of Done

| Check | Criteria |
|-------|----------|
| Evidence collector | Stores raw evidence to S3 with hash; manifest populated correctly |
| Sanitizer | All 6 redaction scenarios pass; fail-closed on high-risk pattern |
| Raw evidence isolation | No raw evidence in LLM context, trace, or API response |
| Cedar policies | All 5 policy tests pass; destructive tool deny test passes |
| Approval flow | Approve/decline endpoints work; approval bound to claim hash + state version |
| Approval expiry | Expired approval → policy DENY |
| Stale approval | Amount changed after approval → policy DENY |
| Autonomy classes | BLACK tools raise `ToolDeniedError`; GREEN tools need no approval |
| Zero unsafe actions | All policy/HITL scenario tests → 0 unsafe external actions |

---

## Post-Implementation Documentation

> Created in `plans/docs/` after phase completion.

- `docs/evidence-pipeline.md` — Evidence collection, storage, sanitization, and manifest design
- `docs/redaction-rules.md` — Complete list of redaction patterns with examples and test cases
- `docs/cedar-policies.md` — Cedar policy documentation with intent, conditions, and test cases
- `docs/hitl-approval-flow.md` — Approval lifecycle, API reference, expiry rules, and security properties
- `docs/autonomy-classes.md` — Tool classification by autonomy class with enforcement mechanism

---

## Risks

| Risk | Mitigation |
|------|-----------|
| Redaction false negatives | Two-pass redaction + high-risk scanner fail-closed; adversarial test suite |
| Cedar policy not enforced | Integration test calls real AgentCore Policy endpoint; not just unit mock |
| Approval race condition | State version binding prevents stale approvals |
| LLM ignores tool restrictions | Restrictions are enforced in deterministic pre-tool hook, not in prompt |
