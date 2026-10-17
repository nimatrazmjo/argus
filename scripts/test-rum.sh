#!/usr/bin/env bash
# scripts/test-rum.sh — Real User Monitoring (RUM) & DOM Session Replay Verification (F017)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F017"

echo "================================================================="
echo "       ARGUS REAL USER MONITORING & REPLAY PROOF (F017)          "
echo "================================================================="

echo "--> [1/4] Ensuring RUM infrastructure is ready via apply-rum.sh..."
"${ROOT_DIR}/deploy/rum/apply-rum.sh"

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

echo "--> [2/4] Executing RUM & session replay E2E controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env RUM_INGEST_TOKEN="${RUM_INGEST_TOKEN}" CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}" python -c "
$(cat "${SCRIPT_DIR}/run_rum_e2e.py")
"

echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
# Archive manifests
cat "${ROOT_DIR}/deploy/rum/rum-collector.yaml" > "${EVIDENCE_DIR}/rum-manifests.yaml"

# Copy generated evidence files from pod /tmp to local evidence dir
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f017/session-replay-transcript.json" "${EVIDENCE_DIR}/session-replay-transcript.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f017/session-replay-proof.html" "${EVIDENCE_DIR}/session-replay-proof.html"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f017/pii-masking-verification.json" "${EVIDENCE_DIR}/pii-masking-verification.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f017/clickhouse-rum-records.json" "${EVIDENCE_DIR}/clickhouse-rum-records.json"

echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in session-replay-transcript.json session-replay-proof.html pii-masking-verification.json clickhouse-rum-records.json rum-manifests.yaml; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: ${art} missing or empty!" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F017 RUM & SESSION REPLAY VERIFIED 100% GREEN!        "
echo "================================================================="
