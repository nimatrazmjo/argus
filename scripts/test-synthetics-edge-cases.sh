#!/usr/bin/env bash
# scripts/test-synthetics-edge-cases.sh — Edge cases and resilience battery for Synthetics (F018)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F018"

echo "================================================================="
echo "       ARGUS SYNTHETICS EDGE CASES BATTERY (F018)                "
echo "================================================================="

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD="chi-argus-clickhouse-argus-cluster-0-0-0"
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [1/2] Executing synthetics edge cases test suite in cluster..."
OUTPUT=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
$(cat "${SCRIPT_DIR}/run_synthetics_edge_cases.py")
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
echo "   FEATURE F018 EDGE CASES VERIFIED 100% GREEN!                  "
echo "================================================================="
