#!/usr/bin/env bash
# scripts/test-synthetics.sh — Functional & E2E verification for Synthetic Canary Probing (F018)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F018"

echo "================================================================="
echo "       ARGUS SYNTHETIC CANARY PROBING PROOF (F018)               "
echo "================================================================="

# 1. Ensure prober is deployed and rules are synced
echo "--> [1/4] Ensuring synthetic prober infrastructure is ready via apply-synthetics.sh..."
"${ROOT_DIR}/deploy/synthetics/apply-synthetics.sh"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD="chi-argus-clickhouse-argus-cluster-0-0-0"
fi

# 2. Execute E2E Verification
SYNTHETIC_BEARER_TOKEN=$(kubectl get secret argus-synthetic-secret -n "${NAMESPACE}" -o jsonpath='{.data.SYNTHETIC_BEARER_TOKEN}' 2>/dev/null | base64 -d || echo "")
echo "--> [2/4] Executing synthetic probing E2E controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env SYNTHETIC_BEARER_TOKEN="${SYNTHETIC_BEARER_TOKEN}" python -c "
$(cat "${SCRIPT_DIR}/run_synthetics_e2e.py")
"

# 3. Collect evidence into evidence dir
echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
mkdir -p "${EVIDENCE_DIR}"

for art in synthetic-metrics-raw.txt synthetic-probe-success.json synthetic-probe-failure.json; do
  kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- cat "/tmp/evidence-f018/${art}" > "${EVIDENCE_DIR}/${art}" 2>/dev/null || true
done
cp "${ROOT_DIR}/deploy/synthetics/synthetic-rules.json" "${EVIDENCE_DIR}/synthetic-rules.json"

# 4. Validate Evidence Files
echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in synthetic-metrics-raw.txt synthetic-probe-success.json synthetic-probe-failure.json synthetic-rules.json; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: Expected artifact missing or empty: ${art}" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F018 SYNTHETICS VERIFIED 100% GREEN!                  "
echo "================================================================="
