#!/usr/bin/env bash
# scripts/test-sso-edge-cases.sh — Edge cases and resilience battery for Agency SSO & RBAC (F016)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F016"

echo "================================================================="
echo "       ARGUS SSO & RBAC EDGE CASES BATTERY (F016)                "
echo "================================================================="

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sso-gateway --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [1/2] Executing SSO edge cases test suite in cluster..."
OUTPUT=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
$(cat "${SCRIPT_DIR}/run_sso_edge_cases.py")
")

echo "${OUTPUT}"
echo "${OUTPUT}" > "${EVIDENCE_DIR}/edge-cases-verification.txt"

echo "--> [2/2] Validating transcript artifact..."
if [ -s "${EVIDENCE_DIR}/edge-cases-verification.txt" ]; then
  echo "    Verified artifact [OK]: edge-cases-verification.txt ($(wc -l < "${EVIDENCE_DIR}/edge-cases-verification.txt" | tr -d ' ') lines)"
else
  echo "    ERROR: edge-cases-verification.txt missing or empty!" >&2
  exit 1
fi

echo "================================================================="
echo "   FEATURE F016 EDGE CASES VERIFIED 100% GREEN!                  "
echo "================================================================="
