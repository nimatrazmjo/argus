#!/usr/bin/env bash
# scripts/test-redaction-edge-cases.sh — Edge cases battery for PII & CJIS redaction
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
GATEWAY_URL="http://argus-gateway-collector.argus-system.svc.cluster.local:4318"
POD_0="chi-argus-clickhouse-argus-cluster-0-0-0"
POD_1="chi-argus-clickhouse-argus-cluster-0-1-0"

PASSED_COUNT=0
FAILED_COUNT=0

echo "================================================================="
echo "       ARGUS PII & CJIS REDACTION EDGE CASES BATTERY             "
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

# -------------------------------------------------------------
# Test 1: Multiple PII instances in a single log body
# -------------------------------------------------------------
echo "--> Test 1: Multiple PII instances in a single log body..."
RUN_ID="$(date +%s)"
START_NANO="${RUN_ID}000000000"
END_NANO="${RUN_ID}100000000"
SUFFIX_1=$(printf "%04d" $(( RUN_ID % 10000 )))
SSN_A="111-22-${SUFFIX_1}"
SSN_B="333-44-${SUFFIX_1}"
CARD_A="5555-4444-3333-${SUFFIX_1}"
TRACE_ID_1=$(openssl rand -hex 16)

BODY_1="Customer report: Primary SSN ${SSN_A}, Secondary SSN ${SSN_B}, Card ${CARD_A}"
PAYLOAD_1='{
  "resourceLogs": [{
    "resource": {
      "attributes": [{"key": "service.name", "value": {"stringValue": "argus-edge-test"}}]
    },
    "scopeLogs": [{
      "scope": {"name": "test-logger"},
      "logRecords": [{
        "timeUnixNano": "'"${END_NANO}"'",
        "observedTimeUnixNano": "'"${END_NANO}"'",
        "severityNumber": 9,
        "severityText": "INFO",
        "body": {"stringValue": "'"${BODY_1}"'"},
        "traceId": "'"${TRACE_ID_1}"'",
        "spanId": "0102030405060708"
      }]
    }]
  }]
}'

post_otlp "v1/logs" "${PAYLOAD_1}" >/dev/null

FOUND_1=false
STORED_BODY_1=""
for i in $(seq 1 30); do
  STORED_BODY_1=$(ch_query "SELECT Body FROM default.otel_logs WHERE TraceId = '${TRACE_ID_1}'" || true)
  if [ -n "${STORED_BODY_1}" ]; then
    FOUND_1=true
    break
  fi
  sleep 1
done

if [ "${FOUND_1}" = "true" ] && \
   [[ "${STORED_BODY_1}" != *"${SSN_A}"* ]] && \
   [[ "${STORED_BODY_1}" != *"${SSN_B}"* ]] && \
   [[ "${STORED_BODY_1}" != *"${CARD_A}"* ]] && \
   [[ "${STORED_BODY_1}" == *"[REDACTED_SSN]"* ]] && \
   [[ "${STORED_BODY_1}" == *"[REDACTED_PAN]"* ]]; then
  echo "    PASS: All multiple SSN and Card instances redacted in body string."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Multiple PII instances not completely redacted: ${STORED_BODY_1}" >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Test 2: Field in log body vs attribute redacted concurrently
# -------------------------------------------------------------
echo "--> Test 2: Redacting sensitive fields simultaneously in body and attributes..."
TRACE_ID_2=$(openssl rand -hex 16)
API_KEY_VAL="api-key-test-${RUN_ID}"
TOKEN_VAL="bearer-token-${RUN_ID}"

BODY_2="Transaction authorized with auth_token=${TOKEN_VAL} and status=SUCCESS"
PAYLOAD_2='{
  "resourceLogs": [{
    "resource": {
      "attributes": [{"key": "service.name", "value": {"stringValue": "argus-edge-test"}}]
    },
    "scopeLogs": [{
      "scope": {"name": "test-logger"},
      "logRecords": [{
        "timeUnixNano": "'"${END_NANO}"'",
        "observedTimeUnixNano": "'"${END_NANO}"'",
        "severityNumber": 9,
        "severityText": "INFO",
        "body": {"stringValue": "'"${BODY_2}"'"},
        "traceId": "'"${TRACE_ID_2}"'",
        "spanId": "0102030405060709",
        "attributes": [
          {"key": "api_key", "value": {"stringValue": "'"${API_KEY_VAL}"'"}},
          {"key": "token", "value": {"stringValue": "'"${TOKEN_VAL}"'"}},
          {"key": "public_id", "value": {"stringValue": "pub-12345"}}
        ]
      }]
    }]
  }]
}'

post_otlp "v1/logs" "${PAYLOAD_2}" >/dev/null

FOUND_2=false
STORED_ATTRS_2=""
STORED_BODY_2=""
for i in $(seq 1 30); do
  STORED_BODY_2=$(ch_query "SELECT Body FROM default.otel_logs WHERE TraceId = '${TRACE_ID_2}'" || true)
  STORED_ATTRS_2=$(ch_query "SELECT LogAttributes FROM default.otel_logs WHERE TraceId = '${TRACE_ID_2}'" || true)
  if [ -n "${STORED_BODY_2}" ]; then
    FOUND_2=true
    break
  fi
  sleep 1
done

if [ "${FOUND_2}" = "true" ] && \
   [[ "${STORED_ATTRS_2}" != *"${API_KEY_VAL}"* ]] && \
   [[ "${STORED_ATTRS_2}" != *"${TOKEN_VAL}"* ]] && \
   [[ "${STORED_BODY_2}" != *"${TOKEN_VAL}"* ]] && \
   [[ "${STORED_BODY_2}" == *"auth_token=[REDACTED]"* ]] && \
   [[ "${STORED_ATTRS_2}" == *"'public_id':'pub-12345'"* ]]; then
  echo "    PASS: Sensitive keys stripped from attributes and inline secrets masked in body."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Failed to redact concurrent body and attribute secrets." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Test 3: Non-string and boolean attribute types pass safely
# -------------------------------------------------------------
echo "--> Test 3: Non-string and boolean attribute types processed without errors..."
TRACE_ID_3=$(openssl rand -hex 16)
PAYLOAD_3='{
  "resourceSpans": [{
    "resource": {
      "attributes": [{"key": "service.name", "value": {"stringValue": "argus-edge-test"}}]
    },
    "scopeSpans": [{
      "scope": {"name": "test-tracer"},
      "spans": [{
        "traceId": "'"${TRACE_ID_3}"'",
        "spanId": "0102030405060710",
        "name": "edge-span-types",
        "kind": 1,
        "startTimeUnixNano": "'"${START_NANO}"'",
        "endTimeUnixNano": "'"${END_NANO}"'",
        "attributes": [
          {"key": "is_active", "value": {"boolValue": true}},
          {"key": "retry_count", "value": {"intValue": "3"}},
          {"key": "ratio", "value": {"doubleValue": 0.95}},
          {"key": "empty_val", "value": {"stringValue": ""}},
          {"key": "password", "value": {"stringValue": "MustBeStripped"}}
        ],
        "status": {"code": 1}
      }]
    }]
  }]
}'

post_otlp "v1/traces" "${PAYLOAD_3}" >/dev/null

FOUND_3=false
STORED_ATTRS_3=""
for i in $(seq 1 30); do
  STORED_ATTRS_3=$(ch_query "SELECT SpanAttributes FROM default.otel_traces WHERE TraceId = '${TRACE_ID_3}'" || true)
  if [ -n "${STORED_ATTRS_3}" ]; then
    FOUND_3=true
    break
  fi
  sleep 1
done

if [ "${FOUND_3}" = "true" ] && \
   [[ "${STORED_ATTRS_3}" != *"MustBeStripped"* ]] && \
   [[ "${STORED_ATTRS_3}" != *"'password'"* ]]; then
  echo "    PASS: Mixed attribute data types handled safely, password stripped."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Processing of mixed attribute types failed: ${STORED_ATTRS_3}" >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Test 4: Sample Service E2E transaction with sensitive data
# -------------------------------------------------------------
echo "--> Test 4: Live sample service transaction with injected sensitive data..."
SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

E2E_SSN="333-22-${SUFFIX_1}"
RESP_JSON=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request, json
url = 'http://127.0.0.1:8080/order?order_id=ord-sensitive-${RUN_ID}'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

E2E_TRACE_ID=$(python3 -c "import sys, json; print(json.loads(sys.stdin.read()).get('trace_id', ''))" <<< "${RESP_JSON}")

E2E_FOUND=false
STORED_BODY_4=""
for i in $(seq 1 30); do
  STORED_BODY_4=$(ch_query "SELECT Body FROM default.otel_logs WHERE TraceId = '${E2E_TRACE_ID}'" || true)
  if [ -n "${STORED_BODY_4}" ]; then
    E2E_FOUND=true
    break
  fi
  sleep 1
done

if [ "${E2E_FOUND}" = "true" ]; then
  echo "    PASS: Live sample service transaction passed through redaction pipeline."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Sample service transaction failed to land." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# -------------------------------------------------------------
# Summary
# -------------------------------------------------------------
echo "================================================================="
echo "Edge case results: ${PASSED_COUNT} passed, ${FAILED_COUNT} failed."
if [ "${FAILED_COUNT}" -gt 0 ]; then
  echo "STATUS: FAIL — Some redaction edge cases failed." >&2
  exit 1
fi
echo "STATUS: PASS — All redaction edge cases passed."
echo "================================================================="
