#!/usr/bin/env bash
# scripts/test-clickhouse-tiering.sh — Functional verification of ClickHouse HA, tiering, and resilience
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
POD="chi-argus-clickhouse-argus-cluster-0-0-0"

echo "================================================================="
echo "    CLICKHOUSE HA, TIERED STORAGE, AND RESILIENCE VERIFICATION   "
echo "================================================================="

# Helper function to execute clickhouse-client queries with retry
ch_query() {
  local sql="$1"
  local attempts=0
  local max_attempts=15
  while [ $attempts -lt $max_attempts ]; do
    if out=$(kubectl exec --request-timeout=30s -n "${NAMESPACE}" "${POD}" -c clickhouse -- clickhouse-client --receive_timeout=30 --send_timeout=30 --password="${PASSWORD}" --query="${sql}" 2>/dev/null); then
      echo "$out"
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 2
  done
  kubectl exec --request-timeout=30s -n "${NAMESPACE}" "${POD}" -c clickhouse -- clickhouse-client --receive_timeout=30 --send_timeout=30 --password="${PASSWORD}" --query="${sql}"
}

# 1. Verify HA Cluster Topology
echo "--> [1/5] Verifying 2-node HA Cluster Topology (system.clusters)..."
ch_query "SYSTEM RELOAD CONFIG" >/dev/null || true
CLUSTER_NODES=0
for i in $(seq 1 30); do
  ch_query "SYSTEM RELOAD CONFIG" >/dev/null || true
  CLUSTER_NODES=$(ch_query "SELECT count() FROM system.clusters WHERE cluster = 'argus-cluster'")
  if [ "${CLUSTER_NODES}" -ge 2 ]; then
    break
  fi
  sleep 1
done
echo "    Nodes in 'argus-cluster': ${CLUSTER_NODES}"
if [ "${CLUSTER_NODES}" -lt 2 ]; then
  echo "    ERROR: Expected at least 2 nodes in 'argus-cluster', found ${CLUSTER_NODES}." >&2
  exit 1
fi
ch_query "SELECT cluster, shard_num, replica_num, host_name, port FROM system.clusters WHERE cluster = 'argus-cluster' FORMAT PrettyCompact"

# 2. Verify Storage Configuration & S3 Disk
echo "--> [2/5] Verifying Storage Policies & Disks (system.disks, system.storage_policies)..."
ch_query "SELECT name, path, formatReadableSize(free_space) as free, type FROM system.disks FORMAT PrettyCompact"
DISKS=$(ch_query "SELECT name FROM system.disks WHERE name IN ('default', 's3_cold')")
if ! echo "$DISKS" | grep -q "s3_cold"; then
  echo "    ERROR: Disk 's3_cold' not found in system.disks." >&2
  exit 1
fi
echo "    Verified 'default' (hot local) and 's3_cold' (object storage) disks."

# 3. Create Tiered Table & Insert Data
echo "--> [3/5] Testing Tiered Storage (insert hot -> verify -> move to s3_cold)..."
ch_query "DROP TABLE IF EXISTS test_tiering"
ch_query "CREATE TABLE test_tiering (id UInt64, metric_name String, value Float64, timestamp DateTime) ENGINE = MergeTree() ORDER BY id SETTINGS storage_policy = 'tiered_hot_cold'"
ch_query "INSERT INTO test_tiering VALUES (1, 'cpu_load', 42.5, now()), (2, 'memory_usage', 88.1, now()), (3, 'disk_io', 12.3, now())"

INITIAL_DISK=$(ch_query "SELECT disk_name FROM system.parts WHERE table = 'test_tiering' AND active = 1 LIMIT 1")
echo "    Initial part landed on disk: '${INITIAL_DISK}'"

PART_NAME=$(ch_query "SELECT name FROM system.parts WHERE table = 'test_tiering' AND active = 1 LIMIT 1")
echo "    Moving part '${PART_NAME}' to disk 's3_cold'..."
ch_query "ALTER TABLE test_tiering MOVE PART '${PART_NAME}' TO DISK 's3_cold'" || true

NEW_DISK=""
for _ in $(seq 1 30); do
  NEW_DISK=$(ch_query "SELECT disk_name FROM system.parts WHERE table = 'test_tiering' AND active = 1 LIMIT 1" || true)
  if [ "$NEW_DISK" = "s3_cold" ]; then
    break
  fi
  sleep 1
done

echo "    Part position after move: '${NEW_DISK}'"
if [ "$NEW_DISK" != "s3_cold" ]; then
  echo "    ERROR: Part move failed. Disk is '${NEW_DISK}', expected 's3_cold'." >&2
  exit 1
fi

COUNT=$(ch_query "SELECT count() FROM test_tiering")
echo "    Queried rows through cold S3 tier: ${COUNT} rows (data readable transparently)"
if [ "$COUNT" -ne 3 ]; then
  echo "    ERROR: Expected 3 rows, found ${COUNT}." >&2
  exit 1
fi

# 4. Test Pod Restart & Data Persistence Resilience
echo "--> [4/5] Testing Pod Restart Resilience (insert -> kill pod -> verify integrity)..."
ch_query "INSERT INTO test_tiering VALUES (999, 'canary_metric', 99.9, now())"
echo "    Inserted canary row (id 999)."

echo "    Simulating node failure: killing pod '${POD}'..."
kubectl delete pod "${POD}" -n "${NAMESPACE}" --wait=true

echo "    Awaiting replacement pod restart and readiness..."
for _ in $(seq 1 30); do
  if kubectl get "pod/${POD}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
kubectl wait --for=condition=Ready "pod/${POD}" -n "${NAMESPACE}" --timeout=120s

echo "    Querying surviving data after pod restart..."
POST_RESTART_COUNT=$(ch_query "SELECT count() FROM test_tiering WHERE id = 999")
TOTAL_COUNT=$(ch_query "SELECT count() FROM test_tiering")
echo "    Total rows after restart: ${TOTAL_COUNT}, Canary row: ${POST_RESTART_COUNT}"

if [ "${POST_RESTART_COUNT}" -ne 1 ]; then
  echo "    ERROR: Data loss detected! Canary row missing after pod restart." >&2
  exit 1
fi

# 5. Clean up test table
ch_query "DROP TABLE test_tiering"
echo "--> [5/5] Test table cleaned up."

echo "================================================================="
echo "STATUS: PASS — ClickHouse HA, Tiering, and Persistence verified."
echo "================================================================="
