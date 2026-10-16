#!/usr/bin/env bash
# scripts/test-paging.sh — Functional & E2E verification for Incident Paging Path (F013)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F013"

echo "================================================================="
echo "       ARGUS INCIDENT PAGING & SERVICENOW VERIFICATION (F013)    "
echo "================================================================="

# 1. Ensure Paging Gateway & ServiceNow Mock are deployed and ready
echo "--> [1/4] Ensuring paging infrastructure is ready via apply-paging.sh..."
"${ROOT_DIR}/deploy/paging/apply-paging.sh"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD="chi-argus-clickhouse-argus-cluster-0-0-0"
fi

# 2. Execute E2E Verification
PAGING_WEBHOOK_TOKEN=$(kubectl get secret argus-paging-secret -n "${NAMESPACE}" -o jsonpath='{.data.PAGING_WEBHOOK_TOKEN}' 2>/dev/null | base64 -d || echo "")
echo "--> [2/4] Executing incident paging E2E controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env PAGING_WEBHOOK_TOKEN="${PAGING_WEBHOOK_TOKEN}" python -c "
$(cat "${SCRIPT_DIR}/run_paging_e2e.py")
"

# 3. Fetch evidence from receiver and gateway into evidence dir
echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
mkdir -p "${EVIDENCE_DIR}"

GATEWAY_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-paging-gateway --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
MOCK_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-servicenow-mock --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

kubectl exec -n "${NAMESPACE}" "${GATEWAY_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:9099/api/status')
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
" > "${EVIDENCE_DIR}/gateway-status.json"

kubectl exec -n "${NAMESPACE}" "${MOCK_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8088/api/now/table/incident')
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print(json.dumps(data.get('result', []), indent=2))
" > "${EVIDENCE_DIR}/servicenow-incidents.json"

kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- cat /tmp/evidence-f013/servicenow-incident-created.json > "${EVIDENCE_DIR}/servicenow-incident-created.json" 2>/dev/null || true
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- cat /tmp/evidence-f013/servicenow-incident-resolved.json > "${EVIDENCE_DIR}/servicenow-incident-resolved.json" 2>/dev/null || true

# 4. Validate Evidence Files
echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in gateway-status.json servicenow-incidents.json servicenow-incident-created.json servicenow-incident-resolved.json; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: Expected artifact missing or empty: ${art}" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F013 INCIDENT PAGING VERIFIED 100% GREEN!             "
echo "================================================================="
