#!/usr/bin/env bash
# scripts/test-correlation-grouping.sh — Alert Correlation & Root-Cause Grouping Verification (F020)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F020"

echo "================================================================="
echo "   ARGUS ALERT CORRELATION & ROOT-CAUSE GROUPING PROOF (F020)    "
echo "================================================================="

echo "--> [1/4] Ensuring Correlation Engine infrastructure is ready via apply-correlation.sh..."
"${ROOT_DIR}/deploy/correlation/apply-correlation.sh"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-correlation-engine --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [2/4] Executing Topological Correlation & Root-Cause E2E suite via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env \
  CORRELATION_URL="http://argus-correlation-engine.${NAMESPACE}.svc.cluster.local:9097" \
  SERVICENOW_URL="http://argus-servicenow-mock.${NAMESPACE}.svc.cluster.local:8088" \
  EVIDENCE_DIR="/tmp/evidence-f020" \
  python -c "
import os
$(cat "${SCRIPT_DIR}/run_correlation_e2e.py")
"

echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
cat "${ROOT_DIR}/deploy/correlation/correlation-workloads.yaml" > "${EVIDENCE_DIR}/correlation-workloads.yaml"

kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f020/correlation-topology.json" "${EVIDENCE_DIR}/correlation-topology.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f020/probable-cause-ranking.json" "${EVIDENCE_DIR}/probable-cause-ranking.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f020/cascading-failure-incident.json" "${EVIDENCE_DIR}/cascading-failure-incident.json"

echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in correlation-topology.json probable-cause-ranking.json cascading-failure-incident.json correlation-workloads.yaml; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: ${art} missing or empty!" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F020 ALERT CORRELATION VERIFIED 100% GREEN!           "
echo "================================================================="
