# Phase 6c — Strands SDK & Bedrock Deep Integration

> **Historical — internal only.** Current product: [docs index](../../../README.md) · [judge-demo.md](../../../judge-demo.md) · [STATUS.md](../STATUS.md).



**Timeline:** Sep 2–6, 2026  
**Status:** `[~] In Progress`  
**Depends on:** Phase 6 ✅, Phase 6b (partial) 🟡  
**Plan file:** `plans/phase-6c-strands-bedrock-integration.md`

---

## Why This Phase Exists

The hackathon is **"AWS Agents for Humans"** judged on Strands Agents usage. Prior to this phase every node in the Recoup graph ran a deterministic Python stub — no LLM, no Strands, no Bedrock. The AgentCore runtime was registered but never invoked. This phase replaces the stubs that represent genuine agent *reasoning* with real Strands `Agent` calls backed by Amazon Bedrock.

**Design principle — deterministic where it matters, LLM where it adds value:**

| Node | Stays deterministic? | Reason |
|---|---|---|
| `normalize_event` | ✅ Yes | Pure parsing — no reasoning needed |
| `incident_correlation` | 🤖 Strands (live mode) | Real reasoning about what happened |
| `sla_contract_resolver` | ✅ Yes | Catalog lookup — deterministic by design |
| `availability_calculator` | ✅ Yes | Financial math must be auditable |
| `evidence_collector` | 🤖 Strands (live mode) | Tool orchestration to gather AWS signals |
| `evidence_sanitizer` | ✅ Yes | Rule-based redaction — must be deterministic |
| `eligibility_reasoner` | 🤖 Strands (live mode) | Legal/contractual reasoning |
| `risk_policy_gate` | ✅ Yes | Cedar policy — must not be LLM-influenced |
| `claim_package_generator` | 🤖 Strands (live mode) | Natural-language claim drafting |
| `case_monitor` | ✅ Yes (stub) | Not yet live — support API |
| **EC2 Demo analysis** | 🤖 Strands (live mode) | Reasoning about idle state + safety |

---

## Architecture

```
GraphState.use_strands = False  ← canonical replay (always deterministic, 20/20)
GraphState.use_strands = True   ← live mode (EC2 demo, future real incidents)

AgentNode.run(state):
    if state.use_strands and strands_fn is not None:
        try:
            return strands_fn(state)   ← real Bedrock call
        except Exception:
            log.warning(...)
            # fall through to stub (graceful degradation)
    return stub_fn(state)             ← deterministic fallback
```

The Strands agents talk to **Amazon Bedrock** via `BedrockModel` from `strands.models`. The model is configured via `BEDROCK_MODEL_ID` in `.env` (default: `us.amazon.nova-pro-v1:0`).

---

## Strands Agents Implemented

### 1. EC2 Stop Decision Agent (`agents/strands_agents.py`)

**Replaces:** hardcoded CPU threshold checks in `EC2DemoAdapter`  
**Called from:** `EC2DemoAdapter.trigger()` when `use_strands=True`  
**Tools exposed to the agent:**
- `get_cpu_utilization(instance_id, days)` → real CloudWatch call
- `get_cloudtrail_events(instance_id, hours)` → real CloudTrail call
- `get_instance_details(instance_id)` → real EC2 describe call

**What it does:** Agent reasons step-by-step about whether the instance is genuinely idle, checks for blocking ownership changes, calculates estimated waste, and returns a structured JSON verdict. The reasoning trace is stored and shown in the UI.

**System prompt excerpt:**
```
You are an AWS cost optimization agent for Recoup.
Analyze the EC2 instance using the available tools.
Determine: Is it idle? Safe to stop? What is the monthly waste?
Think step by step. Use all three tools before concluding.
```

---

### 2. Incident Correlation Agent (`nodes.py`)

**Replaces:** `incident_correlation_stub`  
**Called when:** `state.use_strands=True` (live mode)  
**Tools exposed:** `get_cloudwatch_metrics`, `get_health_event`, `lookup_cloudtrail_events`

**What it does:** Given the incident signal (service, region, time window), the agent calls CloudWatch to get the availability intervals, calls the Health API for the raw event, and calls CloudTrail to verify no customer-caused errors. Returns a structured `IncidentHypothesis`.

**Canonical replay is NOT affected** — `replay_fixtures` are loaded before this node runs, and `use_strands=False` in replay mode.

---

### 3. Eligibility Reasoner Agent (`nodes.py`)

**Replaces:** `eligibility_reasoner_stub`  
**Called when:** `state.use_strands=True` (live mode)  
**Tools:** None (read-only — uses evidence IDs from manifest, never raw content)

**What it does:** Reviews the SLA contract terms, availability result, evidence manifest completeness, and reasons about whether all contractual eligibility requirements are satisfied. Returns a structured `EligibilityAssessment` with confidence score and reasoning.

---

### 4. Claim Package Generator Agent (`nodes.py`)

**Replaces:** `claim_package_generator_stub`  
**Called when:** `state.use_strands=True` and `policy_decision == ALLOW`  
**Tools:** None (uses evidence IDs from sanitized manifest only)

**What it does:** Drafts a professional, concise SLA credit claim letter using only the sanitized evidence IDs. The LLM adds natural-language quality to the claim body.

---

## Files Created / Modified

### New files
- `backend/src/recoup/agents/__init__.py` — package marker
- `backend/src/recoup/agents/strands_agents.py` — all Strands agent definitions, tool decorators, output parsers

### Modified files
- `backend/src/recoup/graph/types.py` — add `use_strands: bool = False` to `GraphState`; add `strands_fn` parameter to `AgentNode`
- `backend/src/recoup/graph/nodes.py` — add `incident_correlation_strands`, `eligibility_reasoner_strands`, `claim_package_generator_strands`
- `backend/src/recoup/graph/recoup_graph.py` — wire `strands_fn` into `AgentNode` definitions
- `backend/src/recoup/adapters/ec2_demo.py` — replace hardcoded checks with `run_ec2_stop_decision_agent()` when `use_strands=True`
- `backend/src/recoup/api/routes/ec2_demo.py` — set `use_strands=settings.recoup_enable_live_aws`
- `backend/src/recoup/api/routes/replay.py` — never set `use_strands=True` (replay stays deterministic)

---

## Remaining Work

- [ ] **Test Strands invocation end-to-end** (~30 min) — with `RECOUP_ENABLE_LIVE_AWS=true`, manually trigger the EC2 demo and confirm that Strands reasoning text appears in the EC2 opportunity card in the UI.
- [ ] **Resolve model ID conflict and verify access** (~15 min) — `strands_agents.py` currently defaults to `us.amazon.nova-pro-v1:0`, but `aws-requirements.md` specifies Claude 3.5 Sonnet (`anthropic.claude-3-5-sonnet-20241022-v2:0`). These conflict. Steps:
  1. Check which models are enabled in account `625962218034` / `us-east-1` via the Bedrock console.
  2. Update `strands_agents.py` to read from `settings.bedrock_model_id` (env var) rather than a hardcoded default — the env var is already defined.
  3. Update `.env.example` `BEDROCK_MODEL_ID` comment to name the confirmed model.
  4. A mismatch silently triggers the graceful fallback with no error — Strands reasoning never appears in the UI without this being correct.
- [ ] **SNS notification on EC2 stop** (~30 min) — P1 from Phase 6b; wire into `ec2_demo.py` after successful stop.

---

## Graceful Degradation

Every Strands call is wrapped in a `try/except`. If Bedrock is unavailable (network, quota, model access), the node falls back to the deterministic stub. This means:
- The demo **never hard-fails** due to a Bedrock timeout
- The 20/20 canonical replay tests are **completely unaffected**
- In the video, if a Bedrock call takes too long, the fallback produces the same correct result

---

## What the Video Shows

**EC2 Demo scene (Scene 4):**
1. Trigger EC2 analysis
2. UI shows "Strands agent reasoning..." with a spinner
3. Agent calls CloudWatch, CloudTrail tools (shown in trace)
4. Agent produces reasoning: *"CPU averaged 0.17% over 7 days. No blocking CloudTrail events. Instance is idle. Estimated waste: $7.59/month. Recommendation: STOP."*
5. Reasoning text shown in the EC2 opportunity card
6. Human approves → instance stops

**SLA Replay scene (Scene 2):**
- Still deterministic (replay mode, use_strands=False)
- The Strands architecture is explained: "In production, when a real Health event fires, the incident_correlation node uses a Strands agent to call CloudWatch and form the hypothesis autonomously."

---

## Env Vars

| Variable | Purpose | Already present? |
|---|---|---|
| `BEDROCK_MODEL_ID` | Model for Strands agents | ✅ Yes |
| `BEDROCK_REGION` | AWS region for Bedrock | ✅ Yes (as `bedrock_region`) |
| `RECOUP_ENABLE_LIVE_AWS` | Gates `use_strands=True` | ✅ Yes |

No new env vars required.

---

## Definition of Done

| Check | Criteria |
|---|---|
| EC2 demo Strands | Agent is invoked and reasoning shown in EC2 card |
| Strands fallback | Disabling Bedrock falls back to stub silently |
| Canonical replay | Still 20/20 deterministic — `use_strands` never set in replay |
| Incident correlation | `strands_fn` wired in `recoup_graph.py` (invoked in live mode) |
| Eligibility reasoner | `strands_fn` wired in `recoup_graph.py` (invoked in live mode) |
| ruff / mypy | 0 errors on all new files |
| Tests | No regression — existing 362 tests still pass |
