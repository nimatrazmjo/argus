#!/usr/bin/env bash
# deploy/aiops/apply-aiops.sh — Deploys AIOps Anomaly Detector daemon in Kubernetes.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "================================================================="
echo "       ARGUS AIOPS ANOMALY & FORECAST MONITORS ROLLOUT (F019)    "
echo "================================================================="

echo "--> [1/3] Updating ConfigMap for Anomaly Detector..."
kubectl create configmap argus-anomaly-detector-code \
  -n "${NAMESPACE}" \
  --from-file=anomaly_detector.py="${SCRIPT_DIR}/anomaly_detector.py" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "--> [2/3] Applying Anomaly Detector workloads (Service & Deployment)..."
kubectl apply -f "${SCRIPT_DIR}/anomaly-workloads.yaml" -n "${NAMESPACE}"

echo "--> [3/3] Awaiting rollout readiness for argus-anomaly-detector..."
kubectl rollout restart deployment/argus-anomaly-detector -n "${NAMESPACE}"
kubectl rollout status deployment/argus-anomaly-detector -n "${NAMESPACE}" --timeout=60s

echo "STATUS: PASS — Anomaly Detector deployed & ready on port 9096."
echo "================================================================="
