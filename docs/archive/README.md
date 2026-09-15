# Documentation archive

**Not maintained for the J-FULL operator path.** Canonical docs live in [docs/README.md](../README.md).

Archived **Sep 11, 2026** — files moved here (not deleted) to keep the active `docs/` folder focused on operator journey + code architecture.

---

## Layout

| Folder | Contents |
|--------|----------|
| [meta/](meta/) | stale-documents (timing/cleanup plans are local-only) |
| [superseded/](superseded/) | Replaced by `recoup-overall-architecture.md` + `*-code-architecture.md` (and `frontend-code-architecture.md` instead of frontend-guide) |
| [optional-depth/](optional-depth/) | SLA replay, graph tools, domain models — code still in repo; optional for judges |
| [ops/](ops/) | IAM, deploy, runbook, cross-account, stopped-services notebook |
| [submit/](submit/) | Video script, Devpost checklist, builder posts, CI guide, disclosure |
| [internal/](internal/) | Local-only: phase tracker, plans, planning `.docx` (see README) |

---

## File index

### meta/

| File | Notes |
|------|--------|
| [stale-documents.md](meta/stale-documents.md) | Stale doc matrix (historical) |

### superseded/

| File | Use instead |
|------|-------------|
| [architecture-overview.md](superseded/architecture-overview.md) | [recoup-overall-architecture.md](../recoup-overall-architecture.md) |
| [agent-graph.md](superseded/agent-graph.md) | [agent-code-architecture.md](../agent-code-architecture.md) + [optional-depth/replay-system.md](optional-depth/replay-system.md) |
| [frontend-guide.md](superseded/frontend-guide.md) | [frontend-code-architecture.md](../frontend-code-architecture.md) |

### optional-depth/

`replay-system.md` · `sla-calculator.md` · `state-machine.md` · `domain-models.md` · `tracing-hooks.md` · `tool-registry.md` · `agentcore-integration.md`

### ops/

`deployment.md` · `infrastructure-runbook.md` · `budget-safety.md` · `iam-roles.md` · `iam-architecture.md` · `cross-account-onboarding.md` · `stopped-services.md`

### submit/

`video-script.md` · `builder-posts.md` · `ci-guide.md` · `DISCLOSURE.md`

### Root of archive/

| File | Notes |
|------|--------|
| [LIVE_SCENARIOS_TODO.md](LIVE_SCENARIOS_TODO.md) | Completed scenario tracker snapshot |

Operator story: [operator-journey.md](../operator-journey.md)
