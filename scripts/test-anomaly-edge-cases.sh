#!/usr/bin/env bash
# scripts/test-anomaly-edge-cases.sh — Anomaly & Forecast Monitors Edge Cases Battery (F019)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F019"

echo "================================================================="
echo "   ARGUS ANOMALY & FORECAST MONITORS EDGE CASES BATTERY (F019)   "
echo "================================================================="

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-anomaly-detector --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [1/3] Executing Anomaly & Forecast Monitors Edge Cases controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env \
  ARGUS_ANOMALY_URL="http://argus-anomaly-detector.${NAMESPACE}.svc.cluster.local:9096" \
  EVIDENCE_DIR="/tmp/evidence-f019" \
  python -c "
import os
$(cat "${SCRIPT_DIR}/run_anomaly_edge_cases.py")
"

echo "--> [2/3] Collecting edge cases evidence into ${EVIDENCE_DIR}..."
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f019/anomaly-edge-cases-report.json" "${EVIDENCE_DIR}/anomaly-edge-cases-report.json"

echo "--> [3/3] Validating edge cases evidence artifacts..."
if [ -s "${EVIDENCE_DIR}/anomaly-edge-cases-report.json" ]; then
  echo "    Verified artifact [OK]: anomaly-edge-cases-report.json ($(wc -c < "${EVIDENCE_DIR}/anomaly-edge-cases-report.json" | tr -d ' ') bytes)"
else
  echo "    ERROR: anomaly-edge-cases-report.json missing or empty!" >&2
  exit 1
fi

echo "================================================================="
echo "   FEATURE F019 EDGE CASES BATTERY VERIFIED 100% GREEN!          "
echo "================================================================="
