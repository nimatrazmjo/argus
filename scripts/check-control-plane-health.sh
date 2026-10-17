#!/usr/bin/env bash
# scripts/check-control-plane-health.sh — Control-plane & etcd latency readiness gate
# Refuses to drive load if kube-apiserver or etcd apply latency is pathological.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX_APISERVER_LATENCY_MS="${MAX_APISERVER_LATENCY_MS:-2500}"
MAX_ETCD_SLOW_APPLIES="${MAX_ETCD_SLOW_APPLIES:-5}"
AUTO_REMEDIATE_ETCD="${AUTO_REMEDIATE_ETCD:-true}"

echo "--> [Control-Plane Gate] Checking kube-apiserver & etcd I/O health..."

# 1. Measure kube-apiserver /readyz latency
measure_apiserver_ms() {
  python3 - <<'PYEOF'
import subprocess, time, sys
t0 = time.monotonic()
res = subprocess.run(
    ["kubectl", "get", "--raw=/readyz", "--request-timeout=5s"],
    capture_output=True,
    text=True,
)
elapsed_ms = int((time.monotonic() - t0) * 1000)
if res.returncode != 0 or "ok" not in res.stdout.lower():
    print(-1)
else:
    print(elapsed_ms)
PYEOF
}

LATENCY_MS=$(measure_apiserver_ms)
if [ "${LATENCY_MS}" -lt 0 ] || [ "${LATENCY_MS}" -gt "${MAX_APISERVER_LATENCY_MS}" ]; then
  echo "    WARN: kube-apiserver /readyz latency is ${LATENCY_MS}ms (threshold: ${MAX_APISERVER_LATENCY_MS}ms)." >&2
  if [ "${AUTO_REMEDIATE_ETCD}" = "true" ] && [ -x "${SCRIPT_DIR}/maintain-etcd.sh" ]; then
    echo "    Triggering automatic etcd compaction & defragmentation..." >&2
    "${SCRIPT_DIR}/maintain-etcd.sh" || true
    sleep 2
    LATENCY_MS=$(measure_apiserver_ms)
  fi
fi

if [ "${LATENCY_MS}" -lt 0 ]; then
  echo "    ERROR: kube-apiserver /readyz is unreachable. Aborting to prevent control-plane overload." >&2
  exit 1
fi

if [ "${LATENCY_MS}" -gt "${MAX_APISERVER_LATENCY_MS}" ]; then
  echo "    ERROR: kube-apiserver /readyz latency (${LATENCY_MS}ms) exceeds floor (${MAX_APISERVER_LATENCY_MS}ms)." >&2
  exit 1
fi

# 2. Check recent etcd logs (last 60s) for multi-second "apply request took too long" warnings
if command -v docker >/dev/null 2>&1; then
  ETCD_CID=$(docker ps -qf "name=k8s_etcd_etcd" 2>/dev/null | head -n 1 || true)
  if [ -n "${ETCD_CID}" ]; then
    SLOW_COUNT=$(docker logs --since 60s "${ETCD_CID}" 2>&1 | { grep -E 'apply request took too long.*"took":"([2-9]\.[0-9]+|[1-9][0-9]+\.[0-9]+)s"' || true; } | wc -l | tr -d ' \n')
    SLOW_COUNT="${SLOW_COUNT:-0}"
    if [ "${SLOW_COUNT}" -gt "${MAX_ETCD_SLOW_APPLIES}" ]; then
      echo "    WARN: Detected ${SLOW_COUNT} multi-second etcd apply stalls in the last 60s." >&2
      if [ "${AUTO_REMEDIATE_ETCD}" = "true" ] && [ -x "${SCRIPT_DIR}/maintain-etcd.sh" ]; then
        echo "    Running etcd compact + defrag remediation..." >&2
        "${SCRIPT_DIR}/maintain-etcd.sh" || true
        sleep 2
      else
        echo "    ERROR: Control-plane etcd disk I/O is saturated (${SLOW_COUNT} slow applies > ${MAX_ETCD_SLOW_APPLIES})." >&2
        exit 1
      fi
    fi
  fi
fi

echo "    [OK] Control-plane health gate passed (apiserver /readyz: ${LATENCY_MS}ms)."
