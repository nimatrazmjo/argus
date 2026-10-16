#!/usr/bin/env bash
# deploy/correlation/apply-correlation.sh — Deploys Topological Alert Correlation Engine in Kubernetes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "================================================================="
echo "   ARGUS TOPOLOGICAL CORRELATION ENGINE ROLLOUT (F020)           "
echo "================================================================="

echo "--> [1/3] Updating ConfigMap for Correlation Engine..."
kubectl create configmap argus-correlation-engine-code \
  -n "${NAMESPACE}" \
  --from-file=correlation_engine.py="${SCRIPT_DIR}/correlation_engine.py" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "--> [2/3] Applying Correlation Engine workloads (Service & Deployment)..."
kubectl apply -f "${SCRIPT_DIR}/correlation-workloads.yaml" -n "${NAMESPACE}"

echo "--> [3/3] Awaiting rollout readiness for argus-correlation-engine..."
kubectl rollout restart deployment/argus-correlation-engine -n "${NAMESPACE}"
kubectl rollout status deployment/argus-correlation-engine -n "${NAMESPACE}" --timeout=60s

echo "STATUS: PASS — Correlation Engine deployed & ready on port 9097."
echo "================================================================="
