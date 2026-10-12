#!/usr/bin/env bash
# scripts/deploy-clickhouse.sh — Deploy ClickHouse HA cluster, Keeper, and S3 Cold Tier
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
MIRROR_REGISTRY="${ARGUS_IMAGE_REGISTRY:-localhost:5001}"

echo "================================================================="
echo "      ARGUS CLICKHOUSE HA & TIERED STORAGE DEPLOYMENT            "
echo "================================================================="

# 1. Validate mirror registry
echo "--> [1/4] Verifying air-gap mirror registry..."
if ! curl -s -f "http://${MIRROR_REGISTRY}/v2/" >/dev/null 2>&1; then
  echo "    ERROR: Mirror registry at ${MIRROR_REGISTRY} is unreachable." >&2
  exit 1
fi

# 2. Deploy S3 cold storage (SeaweedFS)
echo "--> [2/4] Deploying S3 cold tier storage..."
kubectl apply -f deploy/storage/s3-storage.yaml
kubectl rollout status deployment/argus-s3 -n "${NAMESPACE}" --timeout=120s

# 3. Deploy ClickHouse Keeper
echo "--> [3/4] Deploying ClickHouse Keeper cluster..."
kubectl apply -f deploy/clickhouse/clickhouse-keeper.yaml
kubectl wait --for=condition=Ready pod -l clickhouse-keeper.altinity.com/chk=argus-keeper -n "${NAMESPACE}" --timeout=120s

# 4. Deploy ClickHouse HA Installation
echo "--> [4/4] Deploying ClickHouse HA Installation..."
kubectl apply -f deploy/clickhouse/clickhouse-ha.yaml

echo "    Waiting for ClickHouse pods to be ready..."
for pod in chi-argus-clickhouse-argus-cluster-0-0-0 chi-argus-clickhouse-argus-cluster-0-1-0; do
  kubectl wait --for=condition=Ready "pod/${pod}" -n "${NAMESPACE}" --timeout=180s
done

echo "================================================================="
echo "STATUS: PASS — ClickHouse HA and S3 cold tier deployed successfully."
echo "================================================================="
