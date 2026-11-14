#!/usr/bin/env bash
# scripts/deploy-operators.sh — Declarative GitOps deployment of Argus baseline operators
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
VALUES_DIR="deploy/helm/values"
REG="${ARGUS_IMAGE_REGISTRY:-}"   # optional private registry (e.g. ACR); empty = upstream

echo "=== [deploy-operators] Deploying Argus baseline operators to namespace '${NAMESPACE}' ==="

# 2. Ensure target namespace exists
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# 3. Deploy OpenTelemetry Operator
echo "--- Deploying OpenTelemetry Operator ---"
helm upgrade --install opentelemetry-operator open-telemetry/opentelemetry-operator \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_DIR}/opentelemetry-operator-values.yaml" \
  ${REG:+--set manager.image.repository="${REG}/argus/opentelemetry-operator"} \
  ${REG:+--set manager.collectorImage.repository="${REG}/argus/opentelemetry-collector-k8s"} \
  --wait --timeout=300s

# 4. Deploy Altinity ClickHouse Operator
echo "--- Deploying Altinity ClickHouse Operator ---"
helm upgrade --install altinity-clickhouse-operator clickhouse-operator/altinity-clickhouse-operator \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_DIR}/clickhouse-operator-values.yaml" \
  ${REG:+--set operator.image.registry="${REG}/argus" --set operator.image.repository=clickhouse-operator} \
  ${REG:+--set metrics.image.registry="${REG}/argus" --set metrics.image.repository=metrics-exporter} \
  --wait --timeout=300s

# 5. Deploy Prometheus Operator
echo "--- Deploying Prometheus Operator ---"
helm upgrade --install prometheus-operator prometheus-community/kube-prometheus-stack \
  --namespace "${NAMESPACE}" \
  --values "${VALUES_DIR}/kube-prometheus-stack-values.yaml" \
  ${REG:+--set prometheusOperator.image.registry="${REG}/argus" --set prometheusOperator.image.repository=prometheus-operator} \
  ${REG:+--set prometheusOperator.prometheusConfigReloader.image.registry="${REG}/argus" --set prometheusOperator.prometheusConfigReloader.image.repository=prometheus-config-reloader} \
  --wait --timeout=300s

echo "=== [deploy-operators] All operators deployed successfully ==="
helm list -n "${NAMESPACE}"
kubectl get pods -n "${NAMESPACE}"
