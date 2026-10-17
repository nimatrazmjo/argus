#!/usr/bin/env bash
# deploy/llm/apply-llm.sh — Deploys AIOps NL Query & Incident Summarizer in Kubernetes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "================================================================="
echo "   ARGUS AIOPS LLM LAYER & INCIDENT SUMMARIZER ROLLOUT (F021)    "
echo "================================================================="

echo "--> [0/3] Ensuring Kubernetes Secret argus-sso-secret exists..."
if [ -n "${JWT_SECRET:-}" ]; then
  kubectl create secret generic argus-sso-secret \
    -n "${NAMESPACE}" \
    --from-literal=jwt-secret="${JWT_SECRET}" \
    --dry-run=client -o yaml | kubectl apply -f -
elif ! kubectl get secret argus-sso-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f "${ROOT_DIR}/deploy/sso/sso-secret.yaml" -n "${NAMESPACE}"
fi

echo "--> [1/3] Updating ConfigMap for AIOps LLM Service..."
kubectl create configmap argus-aiops-llm-code \
  -n "${NAMESPACE}" \
  --from-file=aiops_llm_service.py="${SCRIPT_DIR}/aiops_llm_service.py" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "--> [2/3] Applying AIOps LLM workloads (Service & Deployment)..."
kubectl apply -f "${SCRIPT_DIR}/aiops-llm-workloads.yaml" -n "${NAMESPACE}"

echo "--> [3/3] Awaiting rollout readiness for argus-aiops-llm..."
kubectl rollout restart deployment/argus-aiops-llm -n "${NAMESPACE}"
kubectl rollout status deployment/argus-aiops-llm -n "${NAMESPACE}" --timeout=60s

echo "STATUS: PASS — AIOps LLM Service deployed & ready on port 9098."
echo "================================================================="
