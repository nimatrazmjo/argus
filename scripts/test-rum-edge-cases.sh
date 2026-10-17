#!/usr/bin/env bash
# scripts/test-rum-edge-cases.sh — Edge cases and resilience battery for Real User Monitoring (F017)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F017"

echo "================================================================="
echo "       ARGUS RUM & SESSION REPLAY EDGE CASES BATTERY (F017)      "
echo "================================================================="

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-rum-collector --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

RUM_INGEST_TOKEN=$(kubectl get secret argus-rum-secret -n "${NAMESPACE}" -o jsonpath='{.data.RUM_INGEST_TOKEN}' 2>/dev/null | base64 -d || echo "")
if [ -z "${RUM_INGEST_TOKEN}" ]; then
  RUM_INGEST_TOKEN=$(kubectl get secret argus-rum-secret -n "${NAMESPACE}" -o jsonpath='{.data.ingest-token}' 2>/dev/null | base64 -d || echo "")
fi
CLICKHOUSE_PASSWORD=$(kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" -o jsonpath='{.data.CLICKHOUSE_PASSWORD}' 2>/dev/null | base64 -d || echo "")

echo "--> [1/2] Executing RUM edge cases test suite in cluster..."
OUTPUT=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env RUM_INGEST_TOKEN="${RUM_INGEST_TOKEN}" CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}" python -c "
$(cat "${SCRIPT_DIR}/run_rum_edge_cases.py")
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
echo "   FEATURE F017 EDGE CASES VERIFIED 100% GREEN!                  "
echo "================================================================="
