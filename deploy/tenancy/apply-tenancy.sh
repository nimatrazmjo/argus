#!/usr/bin/env bash
# deploy/tenancy/apply-tenancy.sh — Applies ClickHouse RLS policies, tenant accounts, and quotas
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"

echo "--> [1/2] Verifying ClickHouse pod availability..."
kubectl rollout status statefulset/chi-argus-clickhouse-argus-cluster-0-0 -n "${NAMESPACE}" --timeout=30s >/dev/null

echo "--> [2/2] Applying tenant accounts, row-level security (RLS), and quotas to ClickHouse..."
kubectl exec -i -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- \
  clickhouse-client --host 127.0.0.1 --user default --password "${PASSWORD}" --multiquery < "${SCRIPT_DIR}/tenant-policies.sql"

echo "    Row policies successfully configured in ClickHouse."
kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- \
  clickhouse-client --host 127.0.0.1 --user default --password "${PASSWORD}" --query "SELECT short_name, database, table, select_filter, apply_to_list FROM system.row_policies"

echo "STATUS: PASS — Multi-tenancy RLS policies and quotas applied."
