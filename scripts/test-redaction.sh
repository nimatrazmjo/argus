#!/usr/bin/env bash
# scripts/test-redaction.sh — Ingest-time PII & CJIS redaction verification
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
GATEWAY_URL="http://argus-gateway-collector.argus-system.svc.cluster.local:4318"
POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"
POD_1="chi-argus-clickhouse-argus-cluster-0-1-0"

echo "================================================================="
echo "       ARGUS PII & CJIS REDACTION VERIFICATION                   "
echo "================================================================="

HAVE_POD_1=false
if kubectl get pod -n "${NAMESPACE}" "${POD_1}" &>/dev/null; then
  HAVE_POD_1=true
fi

ch_query() {
  local sql="$1"
  local res=""
  res=$(kubectl exec -n "${NAMESPACE}" "${POD_0}" -c clickhouse </dev/null -- clickhouse-client --user default --password "${PASSWORD}" --query "${sql}" 2>/dev/null || true)
  if [ -z "$res" ] && [ "${HAVE_POD_1}" = "true" ]; then
    res=$(kubectl exec -n "${NAMESPACE}" "${POD_1}" -c clickhouse </dev/null -- clickhouse-client --user default --password "${PASSWORD}" --query "${sql}" 2>/dev/null || true)
  fi
  echo "$res"
}

post_otlp() {
  local endpoint="$1"
  local json_payload="$2"
  kubectl exec -n "${NAMESPACE}" deploy/argus-s3 </dev/null -- curl -s -f -X POST \
    "${GATEWAY_URL}/${endpoint}" \
    -H "Content-Type: application/json" \
    -d "${json_payload}"
}

RUN_ID="$(date +%s)"
START_NANO="${RUN_ID}000000000"
MID_NANO="${RUN_ID}050000000"
END_NANO="${RUN_ID}100000000"
TRACE_ID=$(openssl rand -hex 16)
SPAN_ID=$(openssl rand -hex 8)

# 1. Define sensitive canary data
RUN_SUFFIX=$(printf "%04d" $(( RUN_ID % 10000 )))
SENSITIVE_SSN="987-65-${RUN_SUFFIX}"
SENSITIVE_PWD="SuperSecretP@ssword_${RUN_ID}"
SENSITIVE_TOKEN="secret-bearer-token-${RUN_ID}"
SENSITIVE_FBI="FBI-CJIS-${RUN_ID}"
SENSITIVE_PAN="4111-2222-3333-${RUN_SUFFIX}"

echo "--> [1/4] Emitting OTLP Trace with sensitive attributes & span events..."
TRACE_PAYLOAD='{
  "resourceSpans": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "argus-redaction-test"}},
        {"key": "k8s.namespace.name", "value": {"stringValue": "argus-system"}},
        {"key": "k8s.node.name", "value": {"stringValue": "docker-desktop"}}
      ]
    },
    "scopeSpans": [{
      "scope": {"name": "test-redaction-tracer"},
      "spans": [{
        "traceId": "'"${TRACE_ID}"'",
        "spanId": "'"${SPAN_ID}"'",
        "name": "redaction-test-span-'"${RUN_ID}"'",
        "kind": 1,
        "startTimeUnixNano": "'"${START_NANO}"'",
        "endTimeUnixNano": "'"${END_NANO}"'",
        "attributes": [
          {"key": "order.id", "value": {"stringValue": "ord-public-123"}},
          {"key": "ssn", "value": {"stringValue": "'"${SENSITIVE_SSN}"'"}},
          {"key": "password", "value": {"stringValue": "'"${SENSITIVE_PWD}"'"}},
          {"key": "note", "value": {"stringValue": "Customer SSN is '"${SENSITIVE_SSN}"'"}}
        ],
        "events": [{
          "timeUnixNano": "'"${MID_NANO}"'",
          "name": "auth_event",
          "attributes": [
            {"key": "token", "value": {"stringValue": "'"${SENSITIVE_TOKEN}"'"}},
            {"key": "cjis_fbi_number", "value": {"stringValue": "'"${SENSITIVE_FBI}"'"}},
            {"key": "event_status", "value": {"stringValue": "authenticated"}}
          ]
        }],
        "status": {"code": 1}
      }]
    }]
  }]
}'

post_otlp "v1/traces" "${TRACE_PAYLOAD}" >/dev/null
echo "    Posted trace ${TRACE_ID} with injected sensitive fields."

echo "--> [2/4] Emitting OTLP Log with sensitive attributes & body text..."
LOG_BODY="Payment processed for account card ${SENSITIVE_PAN} and user ssn ${SENSITIVE_SSN} with password=${SENSITIVE_PWD}"
LOG_PAYLOAD='{
  "resourceLogs": [{
    "resource": {
      "attributes": [
        {"key": "service.name", "value": {"stringValue": "argus-redaction-test"}},
        {"key": "k8s.namespace.name", "value": {"stringValue": "argus-system"}},
        {"key": "k8s.node.name", "value": {"stringValue": "docker-desktop"}}
      ]
    },
    "scopeLogs": [{
      "scope": {"name": "test-redaction-logger"},
      "logRecords": [{
        "timeUnixNano": "'"${END_NANO}"'",
        "observedTimeUnixNano": "'"${END_NANO}"'",
        "severityNumber": 9,
        "severityText": "INFO",
        "body": {"stringValue": "'"${LOG_BODY}"'"},
        "traceId": "'"${TRACE_ID}"'",
        "spanId": "'"${SPAN_ID}"'",
        "attributes": [
          {"key": "safe_field", "value": {"stringValue": "safe_value"}},
          {"key": "cjis_fbi_number", "value": {"stringValue": "'"${SENSITIVE_FBI}"'"}},
          {"key": "password", "value": {"stringValue": "'"${SENSITIVE_PWD}"'"}},
          {"key": "ssn_raw", "value": {"stringValue": "'"${SENSITIVE_SSN}"'"}}
        ]
      }]
    }]
  }]
}'

post_otlp "v1/logs" "${LOG_PAYLOAD}" >/dev/null
echo "    Posted log with injected sensitive fields and PII body."

# 3. Poll ClickHouse until records land
echo "--> [3/4] Awaiting ingestion and verifying proof of absence in ClickHouse..."
DATA_LANDED=false
for i in $(seq 1 30); do
  SPAN_ROW=$(ch_query "SELECT SpanName FROM default.otel_traces WHERE TraceId = '${TRACE_ID}'" || true)
  LOG_ROW=$(ch_query "SELECT Body FROM default.otel_logs WHERE TraceId = '${TRACE_ID}'" || true)

  if [ -n "${SPAN_ROW}" ] && [ -n "${LOG_ROW}" ]; then
    DATA_LANDED=true
    break
  fi
  sleep 1
done

if [ "${DATA_LANDED}" != "true" ]; then
  echo "    ERROR: Telemetry did not land in ClickHouse within 30s." >&2
  exit 1
fi

# 4. Strict assertions: Prove sensitive fields are absent everywhere
echo "--> [4/4] Validating redaction invariants across ClickHouse tables..."

# A. Trace Span Attributes
SPAN_ATTRS=$(ch_query "SELECT SpanAttributes FROM default.otel_traces WHERE TraceId = '${TRACE_ID}'")
echo "    Retrieved SpanAttributes: ${SPAN_ATTRS}"

if [[ "${SPAN_ATTRS}" == *"${SENSITIVE_PWD}"* ]]; then
  echo "    LEAK DETECTED: Password found in SpanAttributes!" >&2
  exit 1
fi
if [[ "${SPAN_ATTRS}" == *"'password'"* || "${SPAN_ATTRS}" == *"'ssn'"* ]]; then
  echo "    LEAK DETECTED: Sensitive keys (password or ssn) still present in SpanAttributes!" >&2
  exit 1
fi
if [[ "${SPAN_ATTRS}" == *"${SENSITIVE_SSN}"* ]]; then
  echo "    LEAK DETECTED: Raw SSN found in SpanAttributes!" >&2
  exit 1
fi
if [[ "${SPAN_ATTRS}" != *"[REDACTED_SSN]"* ]]; then
  echo "    ERROR: Pattern-based SSN mask [REDACTED_SSN] not found in SpanAttributes note!" >&2
  exit 1
fi
echo "    PASS: Sensitive keys stripped and freeform values masked in SpanAttributes."

# B. Span Event Attributes
EVENT_ATTRS=$(ch_query "SELECT Events.Attributes FROM default.otel_traces WHERE TraceId = '${TRACE_ID}'")
echo "    Retrieved Events.Attributes: ${EVENT_ATTRS}"

if [[ "${EVENT_ATTRS}" == *"${SENSITIVE_TOKEN}"* || "${EVENT_ATTRS}" == *"${SENSITIVE_FBI}"* ]]; then
  echo "    LEAK DETECTED: Sensitive values found in Span Events!" >&2
  exit 1
fi
if [[ "${EVENT_ATTRS}" == *"'token'"* || "${EVENT_ATTRS}" == *"'cjis_fbi_number'"* ]]; then
  echo "    LEAK DETECTED: Sensitive keys (token, cjis_fbi_number) found in Span Events!" >&2
  exit 1
fi
echo "    PASS: Sensitive keys and values stripped from Span Events."

# C. Log Attributes and Body
STORED_BODY=$(ch_query "SELECT Body FROM default.otel_logs WHERE TraceId = '${TRACE_ID}'")
STORED_LOG_ATTRS=$(ch_query "SELECT LogAttributes FROM default.otel_logs WHERE TraceId = '${TRACE_ID}'")
echo "    Retrieved Stored Log Body: ${STORED_BODY}"
echo "    Retrieved Stored Log Attributes: ${STORED_LOG_ATTRS}"

if [[ "${STORED_LOG_ATTRS}" == *"${SENSITIVE_PWD}"* || "${STORED_LOG_ATTRS}" == *"${SENSITIVE_FBI}"* ]]; then
  echo "    LEAK DETECTED: Sensitive values found in LogAttributes!" >&2
  exit 1
fi
if [[ "${STORED_LOG_ATTRS}" == *"'password'"* || "${STORED_LOG_ATTRS}" == *"'cjis_fbi_number'"* ]]; then
  echo "    LEAK DETECTED: Sensitive keys (password, cjis_fbi_number) found in LogAttributes!" >&2
  exit 1
fi

if [[ "${STORED_BODY}" == *"${SENSITIVE_PAN}"* ]]; then
  echo "    LEAK DETECTED: Raw Credit Card found in Log Body!" >&2
  exit 1
fi
if [[ "${STORED_BODY}" == *"${SENSITIVE_SSN}"* ]]; then
  echo "    LEAK DETECTED: Raw SSN found in Log Body!" >&2
  exit 1
fi
if [[ "${STORED_BODY}" == *"${SENSITIVE_PWD}"* ]]; then
  echo "    LEAK DETECTED: Raw password found in Log Body!" >&2
  exit 1
fi

if [[ "${STORED_BODY}" != *"[REDACTED_PAN]"* || "${STORED_BODY}" != *"[REDACTED_SSN]"* ]]; then
  echo "    ERROR: Expected redaction markers [REDACTED_PAN] and [REDACTED_SSN] not found in Log Body!" >&2
  exit 1
fi
echo "    PASS: Sensitive keys stripped from LogAttributes, PAN and SSN redacted in Log Body."

# D. Global Database Query Assertion (Zero matches across entire cluster)
GLOBAL_PWD_LEAKS=$(ch_query "SELECT count() FROM default.otel_traces WHERE mapContains(SpanAttributes, 'password') OR mapContains(SpanAttributes, 'ssn')")
GLOBAL_LOG_LEAKS=$(ch_query "SELECT count() FROM default.otel_logs WHERE mapContains(LogAttributes, 'password') OR mapContains(LogAttributes, 'cjis_fbi_number') OR Body LIKE '%${SENSITIVE_SSN}%'")

if [ "${GLOBAL_PWD_LEAKS}" -ne 0 ] || [ "${GLOBAL_LOG_LEAKS}" -ne 0 ]; then
  echo "    LEAK DETECTED in global tables: Trace leaks: ${GLOBAL_PWD_LEAKS}, Log leaks: ${GLOBAL_LOG_LEAKS}" >&2
  exit 1
fi
echo "    PASS: Global database scan confirms zero sensitive records in ClickHouse."

echo "================================================================="
echo "STATUS: PASS — PII and CJIS data provably redacted prior to storage."
echo "================================================================="
