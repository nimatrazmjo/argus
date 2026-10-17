#!/usr/bin/env bash
# deploy/rum/apply-rum.sh — Applies ClickHouse RUM schema, deploys RUM collector, and verifies readiness.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
# shellcheck source=../../scripts/lib/rollout.sh
source "${ROOT_DIR}/scripts/lib/rollout.sh"

echo "================================================================="
echo "       ARGUS REAL USER MONITORING (RUM) & REPLAY ROLLOUT (F017)   "
echo "================================================================="

echo "--> [0/3] Ensuring Kubernetes Secrets (argus-clickhouse-secret, argus-rum-secret)..."
if [ -n "${CLICKHOUSE_PASSWORD:-}" ]; then
  EFFECTIVE_CH_PASS="${CLICKHOUSE_PASSWORD}"
  kubectl create secret generic argus-clickhouse-secret \
    -n "${NAMESPACE}" \
    --from-literal=CLICKHOUSE_PASSWORD="${EFFECTIVE_CH_PASS}" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  if ! kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
    kubectl apply -f "${ROOT_DIR}/deploy/clickhouse/clickhouse-secret.yaml" -n "${NAMESPACE}"
  fi
  EFFECTIVE_CH_PASS="$(kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" -o jsonpath='{.data.CLICKHOUSE_PASSWORD}' | base64 -d)"
  if [ -z "${EFFECTIVE_CH_PASS}" ]; then
    kubectl apply -f "${ROOT_DIR}/deploy/clickhouse/clickhouse-secret.yaml" -n "${NAMESPACE}"
    EFFECTIVE_CH_PASS="$(kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" -o jsonpath='{.data.CLICKHOUSE_PASSWORD}' | base64 -d)"
  fi
fi

if [ -n "${RUM_INGEST_TOKEN:-}" ]; then
  EFFECTIVE_RUM_TOKEN="${RUM_INGEST_TOKEN}"
  kubectl create secret generic argus-rum-secret \
    -n "${NAMESPACE}" \
    --from-literal=ingest-token="${EFFECTIVE_RUM_TOKEN}" \
    --from-literal=RUM_INGEST_TOKEN="${EFFECTIVE_RUM_TOKEN}" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  if ! kubectl get secret argus-rum-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
    kubectl apply -f "${SCRIPT_DIR}/rum-secret.yaml" -n "${NAMESPACE}"
  fi
  EFFECTIVE_RUM_TOKEN="$(kubectl get secret argus-rum-secret -n "${NAMESPACE}" -o jsonpath='{.data.ingest-token}' | base64 -d)"
  if [ -z "${EFFECTIVE_RUM_TOKEN}" ]; then
    kubectl apply -f "${SCRIPT_DIR}/rum-secret.yaml" -n "${NAMESPACE}"
  fi
fi

echo "--> [1/3] Ensuring ClickHouse RUM tables (rum_sessions, rum_events)..."
kubectl exec -i chi-argus-clickhouse-argus-cluster-0-0-0 -n "${NAMESPACE}" -c clickhouse -- \
  clickhouse-client --password "${EFFECTIVE_CH_PASS}" --multiquery < "${SCRIPT_DIR}/rum-schema.sql"

echo "--> [2/3] Updating ConfigMap and applying argus-rum-collector deployment..."
kubectl create configmap argus-rum-collector-code \
  -n "${NAMESPACE}" \
  --from-file=rum_collector.py="${SCRIPT_DIR}/rum_collector.py" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f "${SCRIPT_DIR}/rum-collector.yaml" -n "${NAMESPACE}"

# Roll pods when the collector source changes; the Python process only reads it at startup (#10).
roll_on_code_change "${NAMESPACE}" argus-rum-collector "${SCRIPT_DIR}/rum_collector.py"

echo "--> [3/3] Awaiting rollout readiness for argus-rum-collector..."
kubectl rollout status deployment/argus-rum-collector -n "${NAMESPACE}" --timeout=90s

echo "STATUS: PASS — Real User Monitoring (RUM) Collector deployed & ready."
echo "================================================================="
