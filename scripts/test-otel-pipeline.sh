#!/usr/bin/env bash
# scripts/test-otel-pipeline.sh — Functional verification of OpenTelemetry Collector Pipeline
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"
POD_1="chi-argus-clickhouse-argus-cluster-0-1-0"

echo "================================================================="
echo "   OPENTELEMETRY COLLECTOR PIPELINE FUNCTIONAL VERIFICATION      "
echo "================================================================="

# Helper function to execute clickhouse query across replicas and return combined rows
ch_query_cluster() {
  local sql="$1"
  local r0=""
  local r1=""
  r0=$(kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="${sql}" 2>/dev/null || true)
  r1=$(kubectl exec -n "${NAMESPACE}" "${POD_1}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="${sql}" 2>/dev/null || true)
  echo -e "${r0}\n${r1}" | grep -v '^$' || true
}

# Helper function to post payload via cluster curl (using argus-s3 container)
post_otlp() {
  local endpoint="$1"
  local json_payload="$2"
  kubectl exec -n "${NAMESPACE}" deploy/argus-s3 -- curl -s -f -X POST \
    "http://argus-gateway-collector.argus-system.svc.cluster.local:4318/${endpoint}" \
    -H "Content-Type: application/json" \
    -d "${json_payload}"
}

# 1. Verify Collector Rollout Status
echo "--> [1/5] Verifying Collector Gateway and Node DaemonSet Readiness..."
kubectl rollout status deployment/argus-gateway-collector -n "${NAMESPACE}" --timeout=60s
kubectl rollout status daemonset/argus-node-collector-collector -n "${NAMESPACE}" --timeout=60s
echo "    Gateway Deployment and Node DaemonSet are Ready."

# Ensure ClickHouse replicated tables are active and synchronized with Keeper
for p in "${POD_0}" "${POD_1}"; do
  for tbl in otel_traces otel_logs otel_metrics_sum otel_metrics_gauge; do
    kubectl exec -n "${NAMESPACE}" "${p}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="SYSTEM RESTORE REPLICA default.${tbl}" 2>/dev/null || true
  done
done

# 2. Ingest and Verify Canary Trace with K8s Resource Attributes
echo "--> [2/5] Testing OTLP Trace Ingestion and K8s Attribute Enrichment..."
RUN_ID="$(date +%s)"
TRACE_ID=$(openssl rand -hex 16)
SPAN_ID=$(openssl rand -hex 8)

TRACE_PAYLOAD='{
  "resourceSpans": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "argus-pipeline-test"}},
        {"key": "k8s.namespace.name", "value": {"stringValue": "argus-system"}},
        {"key": "k8s.pod.name", "value": {"stringValue": "test-canary-pod"}},
        {"key": "k8s.node.name", "value": {"stringValue": "docker-desktop"}}
      ]
    },
    "scopeSpans": [{
      "scope": {"name": "test-tracer"},
      "spans": [{
        "traceId": "'"${TRACE_ID}"'",
        "spanId": "'"${SPAN_ID}"'",
        "name": "canary-pipeline-span-'"${RUN_ID}"'",
        "kind": 1,
        "startTimeUnixNano": "1728745200000000000",
        "endTimeUnixNano": "1728745200100000000",
        "attributes": [{"key": "test.id", "value": {"stringValue": "'"${RUN_ID}"'"}}],
        "status": {"code": 1}
      }]
    }]
  }]
}'

post_otlp "v1/traces" "${TRACE_PAYLOAD}" >/dev/null
echo "    Posted trace ${TRACE_ID} to gateway OTLP HTTP receiver (port 4318)."

TRACE_FOUND=false
for i in $(seq 1 15); do
  RES=$(ch_query_cluster "SELECT TraceId, SpanName, ResourceAttributes['k8s.namespace.name'], ResourceAttributes['k8s.node.name'] FROM default.otel_traces WHERE TraceId = '${TRACE_ID}'")
  if [ -n "$RES" ]; then
    TRACE_FOUND=true
    echo "    Found trace in ClickHouse:"
    echo "      ${RES}"
    break
  fi
  sleep 1
done

if [ "$TRACE_FOUND" != "true" ]; then
  echo "    ERROR: Trace ${TRACE_ID} not found in ClickHouse after 15s." >&2
  exit 1
fi

# 3. Ingest and Verify Canary Metric with K8s Resource Attributes
echo "--> [3/5] Testing OTLP Metric Ingestion and K8s Attribute Enrichment..."
METRIC_NAME="canary_requests_${RUN_ID}"
METRIC_PAYLOAD='{
  "resourceMetrics": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "argus-pipeline-test"}},
        {"key": "k8s.namespace.name", "value": {"stringValue": "argus-system"}},
        {"key": "k8s.pod.name", "value": {"stringValue": "test-canary-pod"}},
        {"key": "k8s.node.name", "value": {"stringValue": "docker-desktop"}}
      ]
    },
    "scopeMetrics": [{
      "scope": {"name": "test-meter"},
      "metrics": [{
        "name": "'"${METRIC_NAME}"'",
        "description": "Canary metric for pipeline verification",
        "unit": "1",
        "sum": {
          "aggregationTemporality": 2,
          "isMonotonic": true,
          "dataPoints": [{
            "startTimeUnixNano": "1728745200000000000",
            "timeUnixNano": "1728745200100000000",
            "asDouble": 42.0,
            "attributes": [{"key": "test.id", "value": {"stringValue": "'"${RUN_ID}"'"}}]
          }]
        }
      }]
    }]
  }]
}'

post_otlp "v1/metrics" "${METRIC_PAYLOAD}" >/dev/null
echo "    Posted metric ${METRIC_NAME} to gateway OTLP HTTP receiver (port 4318)."

METRIC_FOUND=false
for i in $(seq 1 15); do
  RES=$(ch_query_cluster "SELECT MetricName, Value, ResourceAttributes['k8s.namespace.name'], ResourceAttributes['k8s.node.name'] FROM default.otel_metrics_sum WHERE MetricName = '${METRIC_NAME}'")
  if [ -n "$RES" ]; then
    METRIC_FOUND=true
    echo "    Found metric in ClickHouse:"
    echo "      ${RES}"
    break
  fi
  sleep 1
done

if [ "$METRIC_FOUND" != "true" ]; then
  echo "    ERROR: Metric ${METRIC_NAME} not found in ClickHouse after 15s." >&2
  exit 1
fi

# 4. Ingest and Verify Canary Log with K8s Resource Attributes
echo "--> [4/5] Testing OTLP Log Ingestion and K8s Attribute Enrichment..."
LOG_BODY="Canary verification log message ${RUN_ID}"
LOG_PAYLOAD='{
  "resourceLogs": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "argus-pipeline-test"}},
        {"key": "k8s.namespace.name", "value": {"stringValue": "argus-system"}},
        {"key": "k8s.pod.name", "value": {"stringValue": "test-canary-pod"}},
        {"key": "k8s.node.name", "value": {"stringValue": "docker-desktop"}}
      ]
    },
    "scopeLogs": [{
      "scope": {"name": "test-logger"},
      "logRecords": [{
        "timeUnixNano": "1728745200100000000",
        "observedTimeUnixNano": "1728745200100000000",
        "severityNumber": 9,
        "severityText": "INFO",
        "body": {"stringValue": "'"${LOG_BODY}"'"},
        "traceId": "'"${TRACE_ID}"'",
        "spanId": "'"${SPAN_ID}"'"
      }]
    }]
  }]
}'

post_otlp "v1/logs" "${LOG_PAYLOAD}" >/dev/null
echo "    Posted log to gateway OTLP HTTP receiver (port 4318)."

LOG_FOUND=false
for i in $(seq 1 15); do
  RES=$(ch_query_cluster "SELECT Body, SeverityText, ResourceAttributes['k8s.namespace.name'], ResourceAttributes['k8s.node.name'] FROM default.otel_logs WHERE Body = '${LOG_BODY}'")
  if [ -n "$RES" ]; then
    LOG_FOUND=true
    echo "    Found log in ClickHouse:"
    echo "      ${RES}"
    break
  fi
  sleep 1
done

if [ "$LOG_FOUND" != "true" ]; then
  echo "    ERROR: Log '${LOG_BODY}' not found in ClickHouse after 15s." >&2
  exit 1
fi

# 5. Verify Continuous Scraped Telemetry (Node DaemonSet live logs & kubelet stats)
echo "--> [5/5] Verifying Node-Level Scraped Telemetry (container logs & kubelet stats)..."
TOTAL_LOGS=0
TOTAL_METRICS=0
for i in $(seq 1 10); do
  c0_l=$(kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="SELECT count() FROM default.otel_logs" 2>/dev/null || echo "0")
  c1_l=$(kubectl exec -n "${NAMESPACE}" "${POD_1}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="SELECT count() FROM default.otel_logs" 2>/dev/null || echo "0")
  TOTAL_LOGS=$((c0_l + c1_l))

  c0_m=$(kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="SELECT count() FROM default.otel_metrics_sum" 2>/dev/null || echo "0")
  c1_m=$(kubectl exec -n "${NAMESPACE}" "${POD_1}" -c clickhouse -- clickhouse-client --password="${PASSWORD}" --query="SELECT count() FROM default.otel_metrics_sum" 2>/dev/null || echo "0")
  TOTAL_METRICS=$((c0_m + c1_m))

  if [ "$TOTAL_LOGS" -ge 10 ] && [ "$TOTAL_METRICS" -ge 10 ]; then
    break
  fi
  sleep 1
done

echo "    Total cluster logs ingested: ${TOTAL_LOGS}"
echo "    Total cluster metrics ingested: ${TOTAL_METRICS}"

if [ "$TOTAL_LOGS" -lt 10 ]; then
  echo "    ERROR: Expected at least 10 logs from DaemonSet scraper, found ${TOTAL_LOGS}." >&2
  exit 1
fi

if [ "$TOTAL_METRICS" -lt 10 ]; then
  echo "    ERROR: Expected at least 10 metrics from DaemonSet kubelet scraper, found ${TOTAL_METRICS}." >&2
  exit 1
fi

echo "================================================================="
echo "STATUS: PASS — OpenTelemetry pipeline successfully verified."
echo "================================================================="
