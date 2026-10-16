#!/usr/bin/env bash
# deploy/sso/apply-sso.sh — Deploys Agency IdP and SSO/RBAC Gateway in Kubernetes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "================================================================="
echo "       ARGUS AGENCY SSO & RBAC GATEWAY ROLLOUT (F016)            "
echo "================================================================="

echo "--> [0/3] Ensuring Kubernetes Secret argus-sso-secret exists..."
if [ -n "${JWT_SECRET:-}" ]; then
  EFFECTIVE_JWT_SECRET="${JWT_SECRET}"
elif kubectl get secret argus-sso-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  EFFECTIVE_JWT_SECRET="$(kubectl get secret argus-sso-secret -n "${NAMESPACE}" -o jsonpath='{.data.jwt-secret}' | base64 -d)"
else
  EFFECTIVE_JWT_SECRET="$(openssl rand -hex 32)"
fi

kubectl create secret generic argus-sso-secret \
  -n "${NAMESPACE}" \
  --from-literal=jwt-secret="${EFFECTIVE_JWT_SECRET}" \
  --dry-run=client -o yaml | kubectl apply -f -

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
