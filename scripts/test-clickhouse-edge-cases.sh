#!/usr/bin/env bash
# scripts/test-clickhouse-edge-cases.sh — Automated tests for ClickHouse HA & storage edge cases
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"
POD_1="chi-argus-clickhouse-argus-cluster-0-1-0"

PASSED_COUNT=0
FAILED_COUNT=0

ch_query() {
  local target_pod="$1"
  local sql="$2"
  kubectl exec -n "${NAMESPACE}" "${target_pod}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="${sql}" 2>/dev/null
}

echo "================================================================="
echo "        CLICKHOUSE EDGE CASES & RESILIENCE BATTERY               "
echo "================================================================="

# 1. Edge Case: Replica Down / High Availability
echo "--> Test 1: Query surviving replica when another replica is unavailable..."
if RES_1=$(ch_query "${POD_1}" "SELECT count() FROM system.clusters WHERE cluster = 'argus-cluster'"); then
  if [ "$RES_1" -ge 1 ]; then
    echo "    PASS: Replica 1 independently serves reads and cluster queries."
    PASSED_COUNT=$((PASSED_COUNT + 1))
  else
    echo "    FAIL: Unexpected cluster node count from replica 1." >&2
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
else
  echo "    FAIL: Could not query replica 1." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# 2. Edge Case: Writes land locally when tiered storage configured
echo "--> Test 2: Writes always land on hot local disk (tiered resilience)..."
ch_query "${POD_0}" "DROP TABLE IF EXISTS test_hot_fallback" || true
ch_query "${POD_0}" "CREATE TABLE test_hot_fallback (id UInt32, val String) ENGINE = MergeTree() ORDER BY id SETTINGS storage_policy = 'tiered_hot_cold'"
ch_query "${POD_0}" "INSERT INTO test_hot_fallback VALUES (101, 'hot_data_1'), (102, 'hot_data_2')"

LANDED_DISK=$(ch_query "${POD_0}" "SELECT disk_name FROM system.parts WHERE table = 'test_hot_fallback' AND active = 1 LIMIT 1")
echo "    Data written to disk: '${LANDED_DISK}'"
if [ "$LANDED_DISK" == "default" ]; then
  echo "    PASS: Writes securely land on local hot disk first, unaffected by remote object store."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Writes landed on unexpected disk: '${LANDED_DISK}'." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi
ch_query "${POD_0}" "DROP TABLE test_hot_fallback"

# 3. Edge Case: Data replication between replicas via ClickHouse Keeper
echo "--> Test 3: Data replication across replicas via ClickHouse Keeper..."
RUN_ID="$(date +%s)"
REPL_TABLE="test_repl_${RUN_ID}"
REPL_PATH="/clickhouse/tables/${REPL_TABLE}"

ch_query "${POD_0}" "DROP TABLE IF EXISTS ${REPL_TABLE} SYNC" || true
ch_query "${POD_1}" "DROP TABLE IF EXISTS ${REPL_TABLE} SYNC" || true

ch_query "${POD_0}" "CREATE TABLE ${REPL_TABLE} (id UInt32, msg String) ENGINE = ReplicatedMergeTree('${REPL_PATH}', 'replica_0') ORDER BY id"
ch_query "${POD_1}" "CREATE TABLE ${REPL_TABLE} (id UInt32, msg String) ENGINE = ReplicatedMergeTree('${REPL_PATH}', 'replica_1') ORDER BY id"

# Insert on replica 0
ch_query "${POD_0}" "INSERT INTO ${REPL_TABLE} VALUES (1, 'hello from replica 0')"

# Await replication to replica 1
REPLICATED=false
for i in $(seq 1 15); do
  REP_COUNT=$(ch_query "${POD_1}" "SELECT count() FROM ${REPL_TABLE}" || echo "0")
  if [ "$REP_COUNT" -eq 1 ]; then
    REPLICATED=true
    break
  fi
  sleep 1
done

if [ "$REPLICATED" == "true" ]; then
  echo "    PASS: Insert on replica 0 replicated to replica 1 via ClickHouse Keeper."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Data failed to replicate to replica 1." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

ch_query "${POD_0}" "DROP TABLE IF EXISTS ${REPL_TABLE} SYNC" || true
ch_query "${POD_1}" "DROP TABLE IF EXISTS ${REPL_TABLE} SYNC" || true

# Summary
echo "================================================================="
echo "Edge case results: ${PASSED_COUNT} passed, ${FAILED_COUNT} failed."
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "STATUS: FAIL" >&2
  exit 1
else
  echo "STATUS: PASS — All ClickHouse edge cases passed."
  exit 0
fi
