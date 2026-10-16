#!/usr/bin/env bash
# deploy/sso/apply-sso.sh — Deploys Agency IdP and SSO/RBAC Gateway in Kubernetes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "================================================================="
echo "       ARGUS AGENCY SSO & RBAC GATEWAY ROLLOUT (F016)            "
echo "================================================================="

echo "--> [1/3] Updating ConfigMaps for Agency IdP and SSO Gateway..."
kubectl create configmap argus-idp-code \
  -n "${NAMESPACE}" \
  --from-file=idp_mock.py="${SCRIPT_DIR}/idp_mock.py" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap argus-sso-gateway-code \
  -n "${NAMESPACE}" \
  --from-file=sso_gateway.py="${SCRIPT_DIR}/sso_gateway.py" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "--> [2/3] Applying SSO workloads (argus-idp and argus-sso-gateway)..."
kubectl apply -f "${SCRIPT_DIR}/sso-workloads.yaml" -n "${NAMESPACE}"

echo "--> [3/3] Awaiting rollout readiness for SSO components..."
kubectl rollout status deployment/argus-idp -n "${NAMESPACE}" --timeout=60s
kubectl rollout status deployment/argus-sso-gateway -n "${NAMESPACE}" --timeout=60s

echo "STATUS: PASS — Agency IdP and SSO/RBAC Gateway deployed & ready."
echo "================================================================="
