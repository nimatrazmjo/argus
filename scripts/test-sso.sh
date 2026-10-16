#!/usr/bin/env bash
# scripts/test-sso.sh — Agency SSO & RBAC End-to-End Verification (F016)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F016"

echo "================================================================="
echo "       ARGUS AGENCY SSO & RBAC VERIFICATION PROOF (F016)         "
echo "================================================================="

echo "--> [1/4] Ensuring SSO infrastructure is ready via apply-sso.sh..."
"${ROOT_DIR}/deploy/sso/apply-sso.sh"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sso-gateway --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [2/4] Executing SSO & RBAC E2E controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
$(cat "${SCRIPT_DIR}/run_sso_e2e.py")
"

echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
cat "${ROOT_DIR}/deploy/sso/sso-workloads.yaml" > "${EVIDENCE_DIR}/sso-manifests.yaml"

kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f016/idp-configuration.json" "${EVIDENCE_DIR}/idp-configuration.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f016/rbac-mapping-proof.json" "${EVIDENCE_DIR}/rbac-mapping-proof.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f016/login-session-transcript.json" "${EVIDENCE_DIR}/login-session-transcript.json"

echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in idp-configuration.json rbac-mapping-proof.json login-session-transcript.json sso-manifests.yaml; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: ${art} missing or empty!" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F016 AGENCY SSO & RBAC VERIFIED 100% GREEN!           "
echo "================================================================="
