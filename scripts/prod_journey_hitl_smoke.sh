#!/usr/bin/env bash
# Operator journey smoke (operator-journey.md §5): approve / investigate / decline on production API.
set -euo pipefail

API="${RECOUP_API_URL:-https://qawwrm7kzy.us-east-1.awsapprunner.com}"

echo "API: $API"
echo "ready: $(curl -sf "$API/health/ready" || echo unavailable)"

SESSION_ID=$(curl -sf -X POST "$API/api/demo/session" \
  -H "Content-Type: application/json" -d '{}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
HDR=(-H "Content-Type: application/json" -H "X-Demo-Session: ${SESSION_ID}")
echo "session: $SESSION_ID"

curl -sf -X POST "$API/api/demo/session/reset?clear_scan_cache=true" "${HDR[@]}" -d '{}' >/dev/null
echo "reset: ok"

SCAN=$(curl -sf -X POST "$API/api/scan/demo" "${HDR[@]}" -d '{}')
FINDING_COUNT=$(echo "$SCAN" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('findings',[])))")
echo "scan findings: $FINDING_COUNT"
test "$FINDING_COUNT" -ge 3

FINDINGS=$(SCAN_JSON="$SCAN" python3 <<'PY'
import json, os
findings = json.loads(os.environ["SCAN_JSON"]).get("findings", [])
picked, seen = [], set()
for f in findings:
    svc = (f.get("service") or "").strip()
    if not svc or svc in seen or not f.get("resource_id"):
        continue
    seen.add(svc)
    picked.append(f)
    if len(picked) >= 3:
        break
if len(picked) < 3:
    raise SystemExit("need 3 distinct services")
print(json.dumps(picked))
PY
)

promote_one() {
  local idx=$1
  local finding
  finding=$(echo "$FINDINGS" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin)[$idx]))")
  curl -sf -X POST "$API/api/scan/findings/promote" "${HDR[@]}" -d "$finding" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['opportunity_id'])"
}

ID_APPROVE=$(promote_one 0)
ID_INVEST=$(promote_one 1)
ID_DECLINE=$(promote_one 2)
echo "opps: approve=$ID_APPROVE investigate=$ID_INVEST decline=$ID_DECLINE"

get_pending() {
  curl -sf "$API/api/approvals/opportunity/$1" "${HDR[@]}"
}

approve_opp() {
  local id=$1
  local p claim amount ver
  p=$(get_pending "$id")
  claim=$(echo "$p" | python3 -c "import sys,json; print(json.load(sys.stdin)['claim_hash'])")
  amount=$(echo "$p" | python3 -c "import sys,json; print(json.load(sys.stdin)['amount'])")
  ver=$(echo "$p" | python3 -c "import sys,json; print(json.load(sys.stdin)['state_version'])")
  curl -sf -X POST "$API/api/approvals/opportunity/$id/approve" "${HDR[@]}" \
    -d "{\"principal\":\"journey-smoke\",\"claim_hash\":\"$claim\",\"amount\":\"$amount\",\"state_version\":$ver,\"notes\":\"J-FULL approve\"}"
}

approve_opp "$ID_APPROVE" >/dev/null
curl -sf -X POST "$API/api/approvals/opportunity/$ID_INVEST/investigate" "${HDR[@]}" \
  -d '{"principal":"journey-smoke","notes":"Investigate Further"}' >/dev/null
curl -sf -X POST "$API/api/approvals/opportunity/$ID_DECLINE/decline" "${HDR[@]}" \
  -d '{"principal":"journey-smoke","notes":"J-FULL decline"}' >/dev/null

state() {
  curl -sf "$API/api/opportunities/$1" "${HDR[@]}" \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('state',''))"
}

S1=$(state "$ID_APPROVE")
S2=$(state "$ID_INVEST")
S3=$(state "$ID_DECLINE")
echo "states: approve=$S1 investigate=$S2 decline=$S3"

case "$S1" in APPROVED|RECOVERED|SUBMITTING|SUBMITTED) ;; *) echo "FAIL approve state $S1"; exit 1 ;; esac
test "$S2" = "NEEDS_FOLLOWUP"
test "$S3" = "DENIED"

echo "PASS — operator journey HITL smoke (approve / investigate / decline)"
