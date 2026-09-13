# Recoup CI Pipeline Guide

**CI provider:** GitHub Actions  
**Config:** `.github/workflows/ci.yml`  
**Triggers:** Push to `main`/`dev`, PR to `main`  
**Last updated:** Sep 11, 2026

---

## Jobs

### 0. `playwright` — Frontend E2E Tests (added Phase 7)

Runs on every push alongside `frontend`. Requires backend to start.

```
# Start backend (auto-started by playwright.config.ts webServer)
cd frontend && npx playwright test --grep @smoke
```

**Test files:** 16 specs · 125 tests (see [release_notes.md](../../../release_notes.md))  
**Tags:** `@smoke` (happy path) · `@full` (edge cases + security)  
**Coverage:** J1–J12 journeys + 13 SEC adversarial scenarios

**Passes when:** All `@smoke` tests pass (0 failures). Full `@full` suite run on PRs to `main`.

See `USER_JOURNEY_CHECKLIST.md` for the per-step coverage map.

### 1. `backend` — Lint & Unit Tests

Runs on every push. No AWS credentials required.

```
ruff check src/ tests/          # style + unused imports
mypy src/recoup/ --strict       # strict type checking (57 source files, 0 errors)
pytest tests/ -W error::DeprecationWarning   # ~416 collected, live-mode skips as configured, zero warnings
pytest tests/unit/test_sla_catalog.py        # SLA catalog integrity
```

**Passes when:** All collected tests green (15 live-mode skipped expected), zero `DeprecationWarning`s, ruff + mypy clean.

### 2. `frontend` — Type-check & Build

```
npx tsc --noEmit     # TypeScript type-check
npm run build        # Next.js production build
```

**Passes when:** Zero TypeScript errors, build succeeds.

### 3. `infra` — CDK Synth

Dry-run CloudFormation synthesis with dummy account/region. No deploy, no AWS credentials.

```
CDK_DEFAULT_ACCOUNT=000000000000
CDK_DEFAULT_REGION=us-east-1
npx cdk synth --all
```

**Passes when:** Both stacks synthesize to valid CloudFormation templates.

### 4. `ship-gates` — Financial Math & Policy Guards

Runs after `backend`. Dedicated gates for competition-critical correctness:

```
pytest tests/unit/test_calculator.py              # golden credit from real billing must be consistent
pytest tests/e2e/test_golden_replay.py            # 20/20 consecutive replay runs pass
pytest tests/adversarial/test_adversarial.py      # zero unsafe actions, no hallucinated evidence
python scripts/run_eval_suite.py --output scorecard.json
python scripts/assert_ship_gates.py scorecard.json  # ship-gate metrics from scorecard JSON
```

**Passes when:** Calculator golden test exact-matches; 20/20 replay determinism confirmed; scorecard gates pass (`all_gates_pass` true) including scenario success, evidence recall, financial math, and `unsafe_actions = 0`.

---

## Adding New Tests

### Unit test (no AWS)
```python
# backend/tests/unit/test_my_feature.py
import pytest

def test_something():
    ...
```

Mark with `@pytest.mark.integration` or `@pytest.mark.slow` if you need to skip in CI.

### Integration test (needs AWS — not run in CI by default)
```python
@pytest.mark.integration
def test_dynamodb_write():
    ...
```

Run locally with:
```bash
pytest tests/ -m integration --aws-profile recoup-sandbox
```

### Adding a new CI job

Edit `.github/workflows/ci.yml`:
```yaml
jobs:
  my-new-job:
    name: My new check
    needs: [backend]        # wait for backend to pass first
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: My check
        run: ...
```

---

## CI Badges

Add to `README.md`:
```markdown
[![CI](https://github.com/swa01wk/recoup/actions/workflows/ci.yml/badge.svg)](https://github.com/swa01wk/recoup/actions/workflows/ci.yml)
```

---

## Troubleshooting

### ruff fails
```bash
cd backend && ruff check src/ tests/ --fix
```

### mypy fails
```bash
cd backend && mypy src/recoup/ --ignore-missing-imports --show-error-codes
```

### CDK synth fails
```bash
cd infra/cdk
CDK_DEFAULT_ACCOUNT=000000000000 CDK_DEFAULT_REGION=us-east-1 npx cdk synth --all
```

### Test fails with DeprecationWarning
All `datetime.utcnow()` calls must be replaced with `datetime.now(timezone.utc)`. Search:
```bash
grep -rn "utcnow()" backend/src/ backend/tests/
```
