#!/usr/bin/env bash
# scripts/test-correlation-grouping-edge-cases.sh — Alert Correlation Edge Cases & Anti-False-Merge Battery (F020)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F020"

echo "================================================================="
echo "   ARGUS CORRELATION EDGE CASES & ANTI-FALSE-MERGE BATTERY       "
echo "================================================================="

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-correlation-engine --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [1/3] Executing Correlation Edge Cases controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env \
  CORRELATION_URL="http://argus-correlation-engine.${NAMESPACE}.svc.cluster.local:9097" \
  SERVICENOW_URL="http://argus-servicenow-mock.${NAMESPACE}.svc.cluster.local:8088" \
  EVIDENCE_DIR="/tmp/evidence-f020" \
  python -c "
import os
$(cat "${SCRIPT_DIR}/run_correlation_edge_cases.py")
"

echo "--> [2/3] Collecting edge cases evidence into ${EVIDENCE_DIR}..."
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f020/correlation-edge-cases-report.json" "${EVIDENCE_DIR}/correlation-edge-cases-report.json"

echo "--> [3/3] Validating edge cases evidence artifacts..."
if [ -s "${EVIDENCE_DIR}/correlation-edge-cases-report.json" ]; then
  echo "    Verified artifact [OK]: correlation-edge-cases-report.json ($(wc -c < "${EVIDENCE_DIR}/correlation-edge-cases-report.json" | tr -d ' ') bytes)"
else
  echo "    ERROR: correlation-edge-cases-report.json missing or empty!" >&2
  exit 1
fi

echo "================================================================="
echo "   FEATURE F020 CORRELATION EDGE CASES VERIFIED 100% GREEN!      "
echo "================================================================="
