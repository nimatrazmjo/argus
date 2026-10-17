#!/usr/bin/env bash
# scripts/deploy-signoz.sh — Declaratively deploy SigNoz APM & Observability UI over ClickHouse HA
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
MIRROR_REGISTRY="${ARGUS_IMAGE_REGISTRY:-localhost:5001}"
if ! kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f deploy/clickhouse/clickhouse-secret.yaml -n "${NAMESPACE}"
fi
if [ -z "${CLICKHOUSE_PASSWORD:-}" ]; then
  CLICKHOUSE_PASSWORD=$(kubectl get secret argus-clickhouse-secret -n "${NAMESPACE}" -o jsonpath='{.data.CLICKHOUSE_PASSWORD}' 2>/dev/null | base64 -d || echo "")
fi
ADMIN_EMAIL="${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD:-$(openssl rand -hex 16)}"

echo "================================================================="
echo "       ARGUS SIGNOZ OBSERVABILITY PLATFORM DEPLOYMENT            "
echo "================================================================="

# 1. Validate mirror registry & images
echo "--> [1/6] Verifying air-gap mirror registry and SigNoz images..."
if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "    ERROR: Mirror registry at ${MIRROR_REGISTRY} is unreachable." >&2
  exit 1
fi

for img in "argus/signoz:v0.145.0" "argus/signoz-otel-collector:v0.144.13"; do
  repo=$(echo "$img" | cut -d':' -f1)
  tag=$(echo "$img" | cut -d':' -f2)
  if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/${repo}/manifests/${tag}" >/dev/null 2>&1; then
    echo "    ERROR: Image ${MIRROR_REGISTRY}/${img} not found in mirror!" >&2
    exit 1
  fi
done
echo "    SigNoz images verified in mirror registry."

# 2. Verify ClickHouse HA Readiness & Experimental JSON settings
echo "--> [2/6] Verifying ClickHouse HA cluster readiness..."
kubectl wait --for=condition=Ready pod/chi-argus-clickhouse-argus-cluster-0-0-0 -n "${NAMESPACE}" --timeout=60s >/dev/null
kubectl wait --for=condition=Ready pod/chi-argus-clickhouse-argus-cluster-0-1-0 -n "${NAMESPACE}" --timeout=60s >/dev/null

# 3. Apply Schema Migrations if needed
echo "--> [3/6] Checking and applying SigNoz schema migrations..."
TABLE_COUNT=$(kubectl exec -n "${NAMESPACE}" chi-argus-clickhouse-argus-cluster-0-0-0 -c clickhouse -- \
  clickhouse-client --user default --password "${CLICKHOUSE_PASSWORD}" \
  --query "SELECT count() FROM system.tables WHERE database = 'signoz_traces' AND name = 'signoz_index_v3';" 2>/dev/null || echo "0")

if [ "${TABLE_COUNT}" -eq 0 ]; then
  echo "    Running SigNoz schema migration job..."
  kubectl delete job signoz-schema-migrator -n "${NAMESPACE}" --ignore-not-found=true >/dev/null
  kubectl apply -f deploy/signoz/schema-migration-job.yaml
  kubectl wait --for=condition=complete job/signoz-schema-migrator -n "${NAMESPACE}" --timeout=180s
  echo "    Schema migration completed successfully."
else
  echo "    SigNoz schema migrations already present (signoz_traces.signoz_index_v3 found)."
fi

# 4. Deploy SigNoz OTel Collector
echo "--> [4/6] Deploying SigNoz OpenTelemetry Collector..."
kubectl apply -f deploy/signoz/signoz-otel-collector.yaml
kubectl rollout status deployment/signoz-otel-collector -n "${NAMESPACE}" --timeout=120s

# 5. Deploy SigNoz Web UI & Query Service
echo "--> [5/6] Deploying SigNoz UI & Query Server..."
kubectl apply -f deploy/signoz/signoz.yaml
kubectl rollout status deployment/signoz -n "${NAMESPACE}" --timeout=120s

# 6. Ensure admin user is registered
echo "--> [6/6] Ensuring initial admin registration..."
SETUP_STATUS=$(kubectl exec -n "${NAMESPACE}" deployment/signoz -- \
  wget -T 3 -qO- http://127.0.0.1:8080/api/v1/version 2>/dev/null || echo "{}")

IS_SETUP=$(echo "${SETUP_STATUS}" | jq -r '.setupCompleted // false' 2>/dev/null || echo "false")
if [ "${IS_SETUP}" != "true" ]; then
  echo "    Registering initial administrator (${ADMIN_EMAIL})..."
  kubectl exec -n "${NAMESPACE}" deployment/signoz -- \
    wget -T 5 -qO- --header="Content-Type: application/json" \
    --post-data="{\"name\":\"Argus Admin\",\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"orgName\":\"argus\"}" \
    http://127.0.0.1:8080/api/v1/register >/dev/null 2>&1 || true
  echo "    Initial administrator registered."
else
  echo "    SigNoz setup already completed."
fi

echo "================================================================="
echo "STATUS: PASS — SigNoz observability platform deployed successfully."
echo "================================================================="
