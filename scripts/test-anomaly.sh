#!/usr/bin/env bash
# scripts/test-anomaly.sh — Anomaly & Forecast Monitors End-to-End Verification (F019)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F019"

echo "================================================================="
echo "   ARGUS ANOMALY & FORECAST MONITORS VERIFICATION PROOF (F019)   "
echo "================================================================="

echo "--> [1/4] Ensuring Anomaly Detector infrastructure is ready via apply-aiops.sh..."
"${ROOT_DIR}/deploy/aiops/apply-aiops.sh"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-anomaly-detector --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [2/4] Executing Anomaly & Forecast Monitors E2E controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env \
  ARGUS_ANOMALY_URL="http://argus-anomaly-detector.${NAMESPACE}.svc.cluster.local:9096" \
  EVIDENCE_DIR="/tmp/evidence-f019" \
  python -c "
import os
$(cat "${SCRIPT_DIR}/run_anomaly_e2e.py")
"

echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
cat "${ROOT_DIR}/deploy/aiops/anomaly-workloads.yaml" > "${EVIDENCE_DIR}/anomaly-workloads.yaml"

kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f019/dynamic-monitor-algorithm.json" "${EVIDENCE_DIR}/dynamic-monitor-algorithm.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f019/false-positive-benchmark.json" "${EVIDENCE_DIR}/false-positive-benchmark.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f019/anomaly-firing-transcript.json" "${EVIDENCE_DIR}/anomaly-firing-transcript.json"

echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in dynamic-monitor-algorithm.json false-positive-benchmark.json anomaly-firing-transcript.json anomaly-workloads.yaml; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: ${art} missing or empty!" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F019 ANOMALY & FORECAST MONITORS VERIFIED 100% GREEN! "
echo "================================================================="
