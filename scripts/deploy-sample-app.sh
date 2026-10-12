#!/usr/bin/env bash
# scripts/deploy-sample-app.sh — Deploy instrumented sample service
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
MIRROR_REGISTRY="${ARGUS_IMAGE_REGISTRY:-localhost:5001}"
IMAGE_TAG="${ARGUS_SAMPLE_IMAGE:-${MIRROR_REGISTRY}/argus/sample-service:1.0.0}"

echo "================================================================="
echo "       ARGUS SAMPLE INSTRUMENTED SERVICE DEPLOYMENT              "
echo "================================================================="

# 1. Verify mirror registry
echo "--> [1/4] Verifying air-gap mirror registry..."
if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "    ERROR: Mirror registry at ${MIRROR_REGISTRY} is unreachable." >&2
  exit 1
fi

# 2. Check or build sample service image
echo "--> [2/4] Verifying sample service container image in mirror..."
if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/argus/sample-service/manifests/1.0.0" >/dev/null 2>&1; then
  echo "    Image not found in mirror. Building and pushing..."
  docker build -t "${IMAGE_TAG}" deploy/sample-app/app
  docker push "${IMAGE_TAG}"
fi
echo "    Verified image ${IMAGE_TAG} in local mirror."

# 3. Apply Kubernetes Deployment & Service
echo "--> [3/4] Applying Kubernetes Deployment and Service..."
kubectl apply -f deploy/sample-app/sample-service.yaml

# 4. Wait for Rollout Readiness
echo "--> [4/4] Awaiting sample service rollout readiness..."
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
