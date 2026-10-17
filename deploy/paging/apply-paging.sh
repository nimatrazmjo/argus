#!/usr/bin/env bash
# deploy/paging/apply-paging.sh — Synchronizes ServiceNow Mock & Paging Gateway in argus-system
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
# shellcheck source=../../scripts/lib/rollout.sh
source "${ROOT_DIR}/scripts/lib/rollout.sh"

echo "--> [1/2] Creating / updating Secrets & ConfigMaps for Paging Gateway and Mock ServiceNow..."
if [ -n "${PAGING_WEBHOOK_TOKEN:-}" ]; then
  kubectl create secret generic argus-paging-secret -n "${NAMESPACE}" \
    --from-literal=PAGING_WEBHOOK_TOKEN="${PAGING_WEBHOOK_TOKEN}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
elif ! kubectl get secret argus-paging-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f "${SCRIPT_DIR}/paging-secret.yaml" -n "${NAMESPACE}" >/dev/null
fi
kubectl create configmap argus-servicenow-mock-code -n "${NAMESPACE}" \
  --from-file=servicenow_mock.py="${SCRIPT_DIR}/servicenow_mock.py" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

kubectl create configmap argus-paging-gateway-code -n "${NAMESPACE}" \
  --from-file=paging_gateway.py="${SCRIPT_DIR}/paging_gateway.py" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo "--> [2/2] Applying Paging Gateway & Mock Deployments and Services..."
kubectl apply -f "${SCRIPT_DIR}/paging-workloads.yaml" >/dev/null

# Roll pods when source changes; the Python processes only read it at startup (#10).
roll_on_code_change "${NAMESPACE}" argus-servicenow-mock "${SCRIPT_DIR}/servicenow_mock.py"
roll_on_code_change "${NAMESPACE}" argus-paging-gateway "${SCRIPT_DIR}/paging_gateway.py"

echo "--> Awaiting readiness of paging workloads..."
kubectl rollout status deployment/argus-servicenow-mock -n "${NAMESPACE}" --timeout=90s >/dev/null
kubectl rollout status deployment/argus-paging-gateway -n "${NAMESPACE}" --timeout=90s >/dev/null

echo "STATUS: PASS — Paging Gateway and ServiceNow Mock are ready in '${NAMESPACE}'."
