#!/usr/bin/env bash
# scripts/test-tenancy.sh — Functional & E2E verification for Multi-Tenancy & Isolation (F015)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F015"

echo "================================================================="
echo "       ARGUS MULTI-TENANCY & DATA ISOLATION PROOF (F015)         "
echo "================================================================="

# 1. Apply ClickHouse tenant accounts, row policies, and quotas
echo "--> [1/4] Ensuring tenant policies and accounts are applied via apply-tenancy.sh..."
"${ROOT_DIR}/deploy/tenancy/apply-tenancy.sh"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD="chi-argus-clickhouse-argus-cluster-0-0-0"
fi

# 2. Execute E2E Isolation Verification
echo "--> [2/4] Executing tenancy isolation E2E controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
$(cat "${SCRIPT_DIR}/run_tenancy_e2e.py")
"

# 3. Collect evidence into evidence dir
echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
mkdir -p "${EVIDENCE_DIR}"

for art in tenant-alpha-isolation.json tenant-beta-isolation.json admin-cross-tenant.json row-policies-catalog.json; do
  kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- cat "/tmp/evidence-f015/${art}" > "${EVIDENCE_DIR}/${art}" 2>/dev/null || true
done

# 4. Validate Evidence Files
echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in tenant-alpha-isolation.json tenant-beta-isolation.json admin-cross-tenant.json row-policies-catalog.json; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: Expected artifact missing or empty: ${art}" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F015 MULTI-TENANCY VERIFIED 100% GREEN!               "
echo "================================================================="
