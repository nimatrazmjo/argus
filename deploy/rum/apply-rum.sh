#!/usr/bin/env bash
# deploy/rum/apply-rum.sh — Applies ClickHouse RUM schema, deploys RUM collector, and verifies readiness.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "================================================================="
echo "       ARGUS REAL USER MONITORING (RUM) & REPLAY ROLLOUT (F017)   "
echo "================================================================="

echo "--> [1/3] Ensuring ClickHouse RUM tables (rum_sessions, rum_events)..."
CH_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=clickhouse-operator -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
kubectl exec -i chi-argus-clickhouse-argus-cluster-0-0-0 -n "${NAMESPACE}" -c clickhouse -- clickhouse-client --password argus123 --multiquery < "${SCRIPT_DIR}/rum-schema.sql"

echo "--> [2/3] Updating ConfigMap and applying argus-rum-collector deployment..."
kubectl create configmap argus-rum-collector-code \
  -n "${NAMESPACE}" \
  --from-file=rum_collector.py="${SCRIPT_DIR}/rum_collector.py" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "${SCRIPT_DIR}/rum-collector.yaml" -n "${NAMESPACE}"

echo "--> [3/3] Awaiting rollout readiness for argus-rum-collector..."
kubectl rollout status deployment/argus-rum-collector -n "${NAMESPACE}" --timeout=60s

echo "STATUS: PASS — Real User Monitoring (RUM) Collector deployed & ready."
echo "================================================================="
