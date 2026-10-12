#!/usr/bin/env bash
# scripts/deploy-operators.sh — Declarative GitOps deployment of Argus baseline operators
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
MIRROR_REGISTRY="${ARGUS_IMAGE_REGISTRY:-localhost:5001}"
VALUES_DIR="deploy/helm/values"

echo "=== [deploy-operators] Deploying Argus baseline operators to namespace '${NAMESPACE}' ==="
echo "Target internal mirror: ${MIRROR_REGISTRY}"

# 1. Verify mirror reachability
if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "ERROR: Mirror registry at http://${MIRROR_REGISTRY}/v2/ is unreachable." >&2
  echo "Run ./deploy/mirror/setup-mirror.sh to initialize the local mirror." >&2
  exit 1
fi
echo "Mirror reachability confirmed."

# 2. Ensure target namespace exists
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# 3. Deploy OpenTelemetry Operator
echo "--- Deploying OpenTelemetry Operator ---"
helm upgrade --install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_DIR}/opentelemetry-operator-values.yaml" \
  --set manager.image.repository="${MIRROR_REGISTRY}/argus/opentelemetry-operator" \
  --set manager.collectorImage.repository="${MIRROR_REGISTRY}/argus/opentelemetry-collector-k8s" \
  --wait --timeout=300s

# 4. Deploy Altinity ClickHouse Operator
echo "--- Deploying Altinity ClickHouse Operator ---"
helm upgrade --install altinity-clickhouse-operator clickhouse-operator/altinity-clickhouse-operator \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_DIR}/clickhouse-operator-values.yaml" \
  --set operator.image.registry="${MIRROR_REGISTRY}/argus" \
  --set metrics.image.registry="${MIRROR_REGISTRY}/argus" \
  --wait --timeout=300s

# 5. Deploy Prometheus Operator
echo "--- Deploying Prometheus Operator ---"
helm upgrade --install prometheus-operator prometheus-community/kube-prometheus-stack \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_DIR}/kube-prometheus-stack-values.yaml" \
  --set prometheusOperator.image.registry="${MIRROR_REGISTRY}/argus" \
  --set prometheusOperator.prometheusConfigReloader.image.registry="${MIRROR_REGISTRY}/argus" \
  --wait --timeout=300s

echo "=== [deploy-operators] All operators deployed successfully ==="
helm list -n "${NAMESPACE}"
kubectl get pods -n "${NAMESPACE}"
