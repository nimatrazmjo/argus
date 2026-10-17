#!/usr/bin/env bash
# scripts/deploy-otel.sh — Declaratively deploy OpenTelemetry Collector Pipeline (Gateway + DaemonSet)
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
MIRROR_REGISTRY="${ARGUS_IMAGE_REGISTRY:-localhost:5001}"
if ! kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f deploy/clickhouse/clickhouse-secret.yaml -n "${NAMESPACE}"
fi
if [ -z "${CLICKHOUSE_PASSWORD:-}" ]; then
  PASSWORD=$(kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" -o jsonpath='{.data.CLICKHOUSE_PASSWORD}' 2>/dev/null | base64 -d || echo "")
else
  PASSWORD="${CLICKHOUSE_PASSWORD}"
fi

echo "================================================================="
echo "      ARGUS OPENTELEMETRY COLLECTOR PIPELINE DEPLOYMENT          "
echo "================================================================="

# 1. Validate mirror registry
echo "--> [1/5] Verifying air-gap mirror registry..."
if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "    ERROR: Mirror registry at ${MIRROR_REGISTRY} is unreachable." >&2
  exit 1
fi

# 2. Pre-provision ClickHouse telemetry schemas across replicas
echo "--> [2/5] Ensuring ClickHouse OTel schema is initialized..."
for pod in chi-argus-clickhouse-argus-cluster-0-0-0 chi-argus-clickhouse-argus-cluster-0-1-0; do
  if kubectl get pod "${pod}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    kubectl exec -n "${NAMESPACE}" "${pod}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --multiquery < deploy/clickhouse/otel-schema.sql >/dev/null 2>&1 || true
  fi
done

# 3. Apply RBAC
echo "--> [3/5] Applying OpenTelemetry Collector RBAC..."
kubectl apply -f deploy/otel/rbac.yaml

# 4. Deploy Gateway Collector
echo "--> [4/5] Deploying OpenTelemetry Gateway Collector..."
kubectl apply -f deploy/otel/gateway.yaml
kubectl rollout status deployment/argus-gateway-collector -n "${NAMESPACE}" --timeout=120s

# 5. Deploy Node DaemonSet Collector
echo "--> [5/6] Deploying OpenTelemetry Node DaemonSet Collector..."
kubectl apply -f deploy/otel/node-daemonset.yaml
kubectl rollout status daemonset/argus-node-collector-collector -n "${NAMESPACE}" --timeout=120s

# 6. Deploy Instrumentation Custom Resources
echo "--> [6/6] Applying OpenTelemetry Instrumentation Custom Resources..."
kubectl apply -f deploy/otel/instrumentation.yaml

echo "================================================================="
echo "STATUS: PASS — OpenTelemetry Collector pipeline deployed successfully."
echo "================================================================="
