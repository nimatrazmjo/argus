#!/usr/bin/env bash
# scripts/deploy-sample-app.sh — Deploy instrumented sample service
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
IMAGE_TAG="${ARGUS_SAMPLE_IMAGE:-argus/sample-service:1.0.0}"

echo "================================================================="
echo "       ARGUS SAMPLE INSTRUMENTED SERVICE DEPLOYMENT              "
echo "================================================================="

# 1-2. Build sample service image locally (Docker Desktop k8s shares the image store)
echo "--> [1/3] Building sample service image ${IMAGE_TAG}..."
docker build -t "${IMAGE_TAG}" deploy/sample-app/app

# 2. Apply Kubernetes Secret, Deployment & Service
echo "--> [2/3] Applying Kubernetes Secret, Deployment and Service..."
if [ -n "${SAMPLE_APP_API_TOKEN:-}" ]; then
  kubectl create secret generic argus-sample-app-secret -n "${NAMESPACE}" \
    --from-literal=SAMPLE_APP_API_TOKEN="${SAMPLE_APP_API_TOKEN}" \
    --dry-run=client -o yaml | kubectl apply -f -
elif ! kubectl get secret argus-sample-app-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f deploy/sample-app/sample-app-secret.yaml -n "${NAMESPACE}"
fi
kubectl apply -f deploy/sample-app/sample-service.yaml

# 3. Wait for Rollout Readiness
echo "--> [3/3] Awaiting sample service rollout readiness..."
kubectl rollout status deployment/argus-sample-service -n "${NAMESPACE}" --timeout=90s

# Verify healthz probe
POD_NAME=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service -o jsonpath='{.items[0].metadata.name}')
HEALTH_STATUS=$(kubectl exec -n "${NAMESPACE}" "${POD_NAME}" -- wget -qO- http://127.0.0.1:8080/healthz 2>/dev/null || echo "failed")
if [[ "${HEALTH_STATUS}" != *"healthy"* ]]; then
  echo "    ERROR: Sample service health check failed: ${HEALTH_STATUS}" >&2
  exit 1
fi

echo "================================================================="
echo "STATUS: PASS — Sample instrumented service deployed successfully."
echo "================================================================="
