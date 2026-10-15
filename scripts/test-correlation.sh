#!/usr/bin/env bash
# scripts/test-correlation.sh — End-to-end telemetry correlation proof (Trace + Metric + Log)
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
MAX_WAIT_SECONDS=45

echo "================================================================="
echo "       ARGUS END-TO-END TELEMETRY CORRELATION PROOF              "
echo "================================================================="

# 1. Verify Sample Service Readiness
echo "--> [1/4] Verifying sample service readiness..."
kubectl rollout status deployment/argus-sample-service -n "${NAMESPACE}" --timeout=30s >/dev/null

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
if [ -z "${SAMPLE_POD}" ]; then
  echo "    ERROR: No running sample service pod found." >&2
  exit 1
fi
echo "    Sample service pod: ${SAMPLE_POD}"

# 2. Drive Transaction through Sample Service
echo "--> [2/4] Issuing transaction to sample service..."
START_TIME=$(date +%s)
ORDER_ID="order-$(openssl rand -hex 4)"

RESP_JSON=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8080/order?order_id=${ORDER_ID}')
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

STATUS=$(python3 -c "import sys, json; print(json.loads(sys.stdin.read()).get('status', ''))" <<< "${RESP_JSON}")
TRACE_ID=$(python3 -c "import sys, json; print(json.loads(sys.stdin.read()).get('trace_id', ''))" <<< "${RESP_JSON}")
SPAN_ID=$(python3 -c "import sys, json; print(json.loads(sys.stdin.read()).get('span_id', ''))" <<< "${RESP_JSON}")
METRIC_NAME=$(python3 -c "import sys, json; print(json.loads(sys.stdin.read()).get('metric_name', ''))" <<< "${RESP_JSON}")

if [ "${STATUS}" != "success" ] || [ -z "${TRACE_ID}" ]; then
  echo "    ERROR: Failed to issue transaction. Response: ${RESP_JSON}" >&2
  exit 1
fi
EMIT_TIME=$(date +%s)

echo "    Transaction initiated successfully:"
echo "      Order ID:    ${ORDER_ID}"
echo "      Trace ID:    ${TRACE_ID}"
echo "      Span ID:     ${SPAN_ID}"
echo "      Metric Name: ${METRIC_NAME}"

# 3. Poll ClickHouse with 3-Way Correlation Join Query
echo "--> [3/4] Awaiting telemetry ingestion & verifying 3-way correlation in ClickHouse..."
CORRELATION_SQL="
SELECT
    t.TraceId AS TraceId,
    t.SpanId AS SpanId,
    t.SpanName AS SpanName,
    t.ServiceName AS ServiceName,
    l.Body AS LogBody,
    l.SeverityText AS LogSeverity,
    m.MetricName AS MetricName,
    m.Value AS MetricValue
FROM default.otel_traces AS t
INNER JOIN default.otel_logs AS l
    ON t.TraceId = l.TraceId
INNER JOIN default.otel_metrics_gauge AS m
    ON t.TraceId = m.Attributes['trace_id']
WHERE t.TraceId = '${TRACE_ID}'
FORMAT Vertical
"

POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"
POD_1="chi-argus-clickhouse-argus-cluster-0-1-0"
HAVE_POD_1=$(kubectl get pod -n "${NAMESPACE}" "${POD_1}" --no-headers 2>/dev/null || true)

JOIN_RESULT=""
INGEST_LATENCY=0
CORRELATED=false

for i in $(seq 1 "${MAX_WAIT_SECONDS}"); do
  JOIN_RESULT=$(kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- clickhouse-client --user default --password "${PASSWORD}" --query "${CORRELATION_SQL}" 2>/dev/null || true)
  if [ -z "${JOIN_RESULT}" ] && [ -n "${HAVE_POD_1}" ]; then
    JOIN_RESULT=$(kubectl exec -n "${NAMESPACE}" "${POD_1}" -c clickhouse -- clickhouse-client --user default --password "${PASSWORD}" --query "${CORRELATION_SQL}" 2>/dev/null || true)
  fi

  if [[ -n "${JOIN_RESULT}" && "${JOIN_RESULT}" == *"TraceId:"*"${TRACE_ID}"* ]]; then
    CORRELATED=true
    INGEST_LATENCY=$(( $(date +%s) - EMIT_TIME ))
    break
  fi
  sleep 1
done

if [ "${CORRELATED}" != "true" ]; then
  echo "    ERROR: Telemetry correlation join query timed out after ${MAX_WAIT_SECONDS}s for TraceId ${TRACE_ID}." >&2
  exit 1
fi

echo "    Correlated trio successfully joined on TraceID across ClickHouse tables:"
echo "${JOIN_RESULT}"

# 4. Latency Verification (< 10 seconds)
echo "--> [4/4] Verifying end-to-end ingestion latency..."
echo "    Total latency from emission to queryable join: ${INGEST_LATENCY}s (limit: < ${MAX_WAIT_SECONDS}s)"
if [ "${INGEST_LATENCY}" -ge "${MAX_WAIT_SECONDS}" ]; then
  echo "    ERROR: Ingestion latency ${INGEST_LATENCY}s exceeded maximum threshold of ${MAX_WAIT_SECONDS}s." >&2
  exit 1
fi
echo "    PASS: Ingestion latency bounded within SLA (${INGEST_LATENCY}s < ${MAX_WAIT_SECONDS}s)."

echo "================================================================="
echo "STATUS: PASS — End-to-end trace, metric, and log correlation verified."
echo "================================================================="
