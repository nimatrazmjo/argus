#!/usr/bin/env bash
# scripts/test-correlation-edge-cases.sh — Edge cases battery for telemetry correlation
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"
POD_1="chi-argus-clickhouse-argus-cluster-0-1-0"

PASSED_COUNT=0
FAILED_COUNT=0

echo "================================================================="
echo "       ARGUS CORRELATION EDGE CASES & RESILIENCE BATTERY         "
echo "================================================================="

ch_query() {
  local sql="$1"
  local res=""
  res=$(kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- clickhouse-client --user default --password "${PASSWORD}" --query "${sql}" 2>/dev/null || true)
  if [ -z "$res" ]; then
    res=$(kubectl exec -n "${NAMESPACE}" "${POD_1}" -c clickhouse -- clickhouse-client --user default --password "${PASSWORD}" --query "${sql}" 2>/dev/null || true)
  fi
  echo "$res"
}

get_sample_pod() {
  kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}'
}

# -------------------------------------------------------------
# Test 1: Dropped Span (Logs and Metrics persist, degrade gracefully)
# -------------------------------------------------------------
echo "--> Test 1: Dropped span handling (telemetry degrades gracefully without crash)..."
SAMPLE_POD=$(get_sample_pod)
RESP_JSON=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8080/order?drop_span=true')
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

TRACE_ID_1=$(echo "${RESP_JSON}" | grep -o '"trace_id": *"[^"]*"' | cut -d'"' -f4)

# Wait for ingestion
FOUND_LOG=false
FOUND_METRIC=false
SPAN_COUNT=0

for i in $(seq 1 10); do
  SPAN_COUNT=$(ch_query "SELECT count() FROM default.otel_traces WHERE TraceId = '${TRACE_ID_1}'" || echo "0")
  LOG_COUNT=$(ch_query "SELECT count() FROM default.otel_logs WHERE TraceId = '${TRACE_ID_1}'" || echo "0")
  METRIC_COUNT=$(ch_query "SELECT count() FROM default.otel_metrics_gauge WHERE Attributes['trace_id'] = '${TRACE_ID_1}'" || echo "0")

  if [ "${LOG_COUNT}" -ge 1 ] && [ "${METRIC_COUNT}" -ge 1 ]; then
    FOUND_LOG=true
    FOUND_METRIC=true
    break
  fi
  sleep 1
done

if [ "${SPAN_COUNT}" -eq 0 ] && [ "${FOUND_LOG}" = "true" ] && [ "${FOUND_METRIC}" = "true" ]; then
  echo "    PASS: Dropped span handled correctly: zero span rows, log & metric successfully ingested and correlated."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Unexpected counts for dropped span (Spans: ${SPAN_COUNT}, Log: ${FOUND_LOG}, Metric: ${FOUND_METRIC})" >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Test 2: Log without TraceId (Missing ID does not break ingestion)
# -------------------------------------------------------------
echo "--> Test 2: Log without TraceId (missing correlation ID degrades gracefully)..."
SAMPLE_POD=$(get_sample_pod)
ORDER_ID_2="order-notrace-$(openssl rand -hex 4)"
RESP_JSON=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8080/order?no_trace_id=true&order_id=${ORDER_ID_2}')
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

LOG_FOUND_2=false
for i in $(seq 1 10); do
  LOG_ROW=$(ch_query "SELECT TraceId, Body FROM default.otel_logs WHERE Body LIKE '%${ORDER_ID_2}%'" || true)
  if [ -n "${LOG_ROW}" ]; then
    LOG_FOUND_2=true
    break
  fi
  sleep 1
done

if [ "${LOG_FOUND_2}" = "true" ]; then
  echo "    PASS: Log with empty TraceId ingested without collector or database errors."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Log without TraceId was not ingested." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Test 3: Clock Skew Handling (Telemetries with skewed timestamp)
# -------------------------------------------------------------
echo "--> Test 3: Clock skew handling (telemetry offset by ±120 seconds)..."
SAMPLE_POD=$(get_sample_pod)
RESP_JSON=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8080/order?skew_seconds=120')
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

TRACE_ID_3=$(echo "${RESP_JSON}" | grep -o '"trace_id": *"[^"]*"' | cut -d'"' -f4)

SKEW_CORRELATED=false
for i in $(seq 1 10); do
  JOIN_RESULT=$(ch_query "
    SELECT t.TraceId, l.SeverityText, m.Value
    FROM default.otel_traces AS t
    JOIN default.otel_logs AS l ON t.TraceId = l.TraceId
    JOIN default.otel_metrics_gauge AS m ON t.TraceId = m.Attributes['trace_id']
    WHERE t.TraceId = '${TRACE_ID_3}'
  " || true)

  if [ -n "${JOIN_RESULT}" ]; then
    SKEW_CORRELATED=true
    break
  fi
  sleep 1
done

if [ "${SKEW_CORRELATED}" = "true" ]; then
  echo "    PASS: Time-skewed telemetry ingested and correlated successfully across all 3 tables."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Time-skewed telemetry failed to correlate in ClickHouse." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Test 4: Sample Service Pod Restart and Reconnection
# -------------------------------------------------------------
echo "--> Test 4: Sample service pod restart and pipeline reconnection..."
CURRENT_POD=$(get_sample_pod)
echo "    Terminating sample pod '${CURRENT_POD}'..."
kubectl delete pod "${CURRENT_POD}" -n "${NAMESPACE}" --wait=true >/dev/null

echo "    Awaiting replacement pod readiness..."
kubectl rollout status deployment/argus-sample-service -n "${NAMESPACE}" --timeout=60s >/dev/null

NEW_POD=$(get_sample_pod)
echo "    Replacement pod running: '${NEW_POD}'"

RESTART_RESP=$(kubectl exec -n "${NAMESPACE}" "${NEW_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8080/order')
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

RESTART_TRACE_ID=$(echo "${RESTART_RESP}" | grep -o '"trace_id": *"[^"]*"' | cut -d'"' -f4)

RESTART_CORRELATED=false
for i in $(seq 1 30); do
  JOIN_RESULT=$(ch_query "
    SELECT t.TraceId, l.SeverityText, m.Value
    FROM default.otel_traces AS t
    JOIN default.otel_logs AS l ON t.TraceId = l.TraceId
    JOIN default.otel_metrics_gauge AS m ON t.TraceId = m.Attributes['trace_id']
    WHERE t.TraceId = '${RESTART_TRACE_ID}'
  " || true)

  if [ -n "${JOIN_RESULT}" ]; then
    RESTART_CORRELATED=true
    break
  fi
  sleep 1
done

if [ "${RESTART_CORRELATED}" = "true" ]; then
  echo "    PASS: Sample service resumed telemetry correlation immediately after pod restart."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Telemetry correlation failed after pod restart." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Summary
# -------------------------------------------------------------
echo "================================================================="
echo "Edge case results: ${PASSED_COUNT} passed, ${FAILED_COUNT} failed."
if [ "${FAILED_COUNT}" -gt 0 ]; then
  echo "STATUS: FAIL — Some edge cases failed." >&2
  exit 1
fi
echo "STATUS: PASS — All correlation edge cases passed."
echo "================================================================="
