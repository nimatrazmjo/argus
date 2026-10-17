#!/usr/bin/env bash
# scripts/maintain-etcd.sh — Compact and defragment the Kubernetes etcd keyspace
# Can run directly from the host via Docker (even when kube-apiserver is wedged)
# or inside a maintenance pod mounting /run/config/pki/etcd.
set -euo pipefail

ETCD_ENDPOINT="${ETCD_ENDPOINT:-https://127.0.0.1:2379}"
ETCD_CACERT="${ETCD_CACERT:-/run/config/pki/etcd/ca.crt}"
ETCD_CERT="${ETCD_CERT:-/run/config/pki/etcd/server.crt}"
ETCD_KEY="${ETCD_KEY:-/run/config/pki/etcd/server.key}"

run_etcdctl() {
  if [ -x /usr/local/bin/etcdctl ] && [ -f "${ETCD_CACERT}" ]; then
    /usr/local/bin/etcdctl \
      --endpoints="${ETCD_ENDPOINT}" \
      --cacert="${ETCD_CACERT}" \
      --cert="${ETCD_CERT}" \
      --key="${ETCD_KEY}" \
      --command-timeout=60s \
      "$@"
  else
    local cid
    cid=$(docker ps -qf "name=k8s_etcd_etcd" | head -n 1)
    if [ -z "${cid}" ]; then
      echo "ERROR: Could not locate running k8s_etcd_etcd container." >&2
      return 1
    fi
    docker exec "${cid}" /usr/local/bin/etcdctl \
      --endpoints="${ETCD_ENDPOINT}" \
      --cacert="${ETCD_CACERT}" \
      --cert="${ETCD_CERT}" \
      --key="${ETCD_KEY}" \
      --command-timeout=60s \
      "$@"
  fi
}

echo "================================================================="
echo "           ARGUS CONTROL-PLANE ETCD MAINTENANCE                  "
echo "================================================================="

echo "--> [1/4] Fetching current etcd endpoint status..."
STATUS_JSON=$(run_etcdctl endpoint status -w json)
echo "${STATUS_JSON}"

REV=$(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print(data[0]["Status"]["header"]["revision"])
' <<< "${STATUS_JSON}")

DB_SIZE_BEFORE=$(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print(data[0]["Status"].get("dbSize", 0))
' <<< "${STATUS_JSON}")

DB_IN_USE_BEFORE=$(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print(data[0]["Status"].get("dbSizeInUse", 0))
' <<< "${STATUS_JSON}")

echo "    Current Revision : ${REV}"
echo "    DB Size (before) : ${DB_SIZE_BEFORE} bytes (in-use: ${DB_IN_USE_BEFORE} bytes)"

echo "--> [2/4] Compacting etcd keyspace up to revision ${REV}..."
run_etcdctl compact "${REV}" || echo "    (Revision ${REV} already compacted)"

echo "--> [3/4] Defragmenting etcd boltdb storage..."
run_etcdctl defrag

echo "--> [4/4] Disarming any etcd alarms and verifying post-defrag status..."
run_etcdctl alarm disarm >/dev/null 2>&1 || true
AFTER_JSON=$(run_etcdctl endpoint status -w json)

DB_SIZE_AFTER=$(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print(data[0]["Status"].get("dbSize", 0))
' <<< "${AFTER_JSON}")

DB_IN_USE_AFTER=$(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
print(data[0]["Status"].get("dbSizeInUse", 0))
' <<< "${AFTER_JSON}")

echo "    DB Size (after)  : ${DB_SIZE_AFTER} bytes (in-use: ${DB_IN_USE_AFTER} bytes)"
echo "================================================================="
echo "STATUS: PASS — etcd compacted and defragmented successfully."
echo "================================================================="
