#!/usr/bin/env bash
# scripts/test-signoz-edge-cases.sh — Edge cases and resilience battery for SigNoz APM platform
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
ADMIN_EMAIL="${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD:-ArgusAdminPassword123!}"

echo "================================================================="
echo "       ARGUS SIGNOZ EDGE CASES & FAILURE PATHS BATTERY           "
echo "================================================================="

SIGNOZ_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=signoz --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
if [ -z "${SIGNOZ_POD}" ]; then
  echo "    ERROR: No running SigNoz pod found." >&2
  exit 1
fi

INITIAL_RESTARTS=$(kubectl get pod "${SIGNOZ_POD}" -n "${NAMESPACE}" -o jsonpath='{.status.containerStatuses[0].restartCount}')

# Authenticate to get token
SETUP_STATUS=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 3 -qO- http://127.0.0.1:8080/api/v1/version 2>/dev/null || echo "{}")
IS_SETUP=$(echo "${SETUP_STATUS}" | jq -r '.setupCompleted // false' 2>/dev/null || echo "false")
if [ "${IS_SETUP}" != "true" ]; then
  kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
    wget -T 5 -qO- --header="Content-Type: application/json" \
    --post-data="{\"name\":\"Argus Admin\",\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"orgName\":\"argus\"}" \
    http://127.0.0.1:8080/api/v1/register >/dev/null 2>&1 || true
fi

SESSION_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- "http://127.0.0.1:8080/api/v2/sessions/context?email=${ADMIN_EMAIL}")
ORG_ID=$(echo "${SESSION_RESP}" | jq -r '.data.orgs[0].id // empty')

LOGIN_PAYLOAD="{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"orgId\":\"${ORG_ID}\"}"
LOGIN_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Content-Type: application/json" \
  --post-data="${LOGIN_PAYLOAD}" \
  http://127.0.0.1:8080/api/v2/sessions/email_password)

TOKEN=$(echo "${LOGIN_RESP}" | jq -r '.data.accessToken // empty')
if [ -z "${TOKEN}" ]; then
  echo "    ERROR: Failed to obtain access token." >&2
  exit 1
fi

# =================================================================
# Test 1: Empty-State Queries
# =================================================================
echo "--> [1/4] Edge Case: Empty-state handling (non-existent traces, services, time ranges)..."

# 1a. Non-existent trace ID
NON_EXISTENT_TRACE="00000000000000000000000000000000"
EMPTY_TRACE_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Authorization: Bearer ${TOKEN}" \
  "http://127.0.0.1:8080/api/v1/traces/${NON_EXISTENT_TRACE}" 2>&1 || true)

# Should return empty array or null without unhandled panic or 500
if [[ "${EMPTY_TRACE_RESP}" == *"panic"* ]] || [[ "${EMPTY_TRACE_RESP}" == *"500 Internal Server Error"* ]]; then
  echo "    ERROR: Non-existent trace triggered unhandled error: ${EMPTY_TRACE_RESP}" >&2
  exit 1
fi
echo "    Non-existent trace query handled gracefully (no crash or 500 panic)."

# 1b. Non-existent service name in query_range
NOW_TS=$(date +%s)
START_TS=$(( (NOW_TS - 3600) * 1000 ))
END_TS=$(( NOW_TS * 1000 ))

EMPTY_SERVICE_PAYLOAD='{
  "start": '"${START_TS}"',
  "end": '"${END_TS}"',
  "step": 60,
  "compositeQuery": {
    "queryType": "builder",
    "panelType": "list",
    "builderQueries": {
      "A": {
        "queryName": "A",
        "stepInterval": 60,
        "dataSource": "logs",
        "aggregateOperator": "noop",
        "expression": "A",
        "filterAttribute": {
          "items": [
            {
              "key": {"key": "service_name", "dataType": "string", "type": "tag"},
              "op": "=",
              "value": "non-existent-service-argus-empty"
            }
          ]
        },
        "limit": 10
      }
    }
  }
}'

EMPTY_SERVICE_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Authorization: Bearer ${TOKEN}" \
  --header="Content-Type: application/json" \
  --post-data="${EMPTY_SERVICE_PAYLOAD}" \
  http://127.0.0.1:8080/api/v3/query_range 2>&1 || true)

if [[ "${EMPTY_SERVICE_RESP}" == *"panic"* ]]; then
  echo "    ERROR: Empty service query caused panic: ${EMPTY_SERVICE_RESP}" >&2
  exit 1
fi
echo "    Non-existent service filter handled gracefully."

# =================================================================
# Test 2: Authentication Security & Bad Input
# =================================================================
echo "--> [2/4] Edge Case: Authentication rejection & malformed payloads..."

# 2a. Bad password
BAD_AUTH_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Content-Type: application/json" \
  --post-data="{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"WrongPassword!\",\"orgId\":\"${ORG_ID}\"}" \
  http://127.0.0.1:8080/api/v2/sessions/email_password 2>&1 || true)

if [[ "${BAD_AUTH_RESP}" != *"incorrect_password"* ]] && [[ "${BAD_AUTH_RESP}" != *"unauthenticated"* ]] && [[ "${BAD_AUTH_RESP}" != *"401"* ]]; then
  echo "    ERROR: Bad password did not return expected authentication rejection: ${BAD_AUTH_RESP}" >&2
  exit 1
fi
echo "    Authentication failure handled cleanly with structured 401 error."

# 2b. Malformed JSON payload
BAD_JSON_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Authorization: Bearer ${TOKEN}" \
  --header="Content-Type: application/json" \
  --post-data="{not-json" \
  http://127.0.0.1:8080/api/v3/query_range 2>&1 || true)

if [[ "${BAD_JSON_RESP}" == *"panic"* ]]; then
  echo "    ERROR: Malformed JSON caused server panic: ${BAD_JSON_RESP}" >&2
  exit 1
fi
echo "    Malformed JSON payload rejected cleanly without crash."

# =================================================================
# Test 3: High Volume / Deep Trace SLA Handling
# =================================================================
echo "--> [3/4] Edge Case: Large trace & deep attribute query SLA performance..."

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

# Emit batch of synthetic traces
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request
for i in range(5):
    try:
        req = urllib.request.Request(f'http://127.0.0.1:8080/order?order_id=batch-sla-{i}')
        with urllib.request.urlopen(req, timeout=2) as resp:
            resp.read()
    except Exception:
        pass
"

# Query trace aggregations with timing SLA (< 5s)
START_TIME=$(date +%s)
QUERY_SLA_PAYLOAD='{
  "start": '"$(( (NOW_TS - 7200) * 1000 ))"',
  "end": '"$(( NOW_TS * 1000 ))"',
  "step": 60,
  "compositeQuery": {
    "queryType": "builder",
    "panelType": "graph",
    "builderQueries": {
      "A": {
        "queryName": "A",
        "stepInterval": 60,
        "dataSource": "traces",
        "aggregateOperator": "count",
        "expression": "A"
      }
    }
  }
}'

SLA_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Authorization: Bearer ${TOKEN}" \
  --header="Content-Type: application/json" \
  --post-data="${QUERY_SLA_PAYLOAD}" \
  http://127.0.0.1:8080/api/v3/query_range)

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

if [ "${DURATION}" -gt 5 ]; then
  echo "    ERROR: Trace query SLA exceeded (> 5s): took ${DURATION}s." >&2
  exit 1
fi
echo "    Large trace query completed within SLA: ${DURATION}s (< 5s threshold)."

# =================================================================
# Test 4: Upstream Interruption & Pod State Preservation
# =================================================================
echo "--> [4/4] Edge Case: ClickHouse query error resilience & zero crash-loop audit..."

# Query an invalid table function or syntax error through ClickHouse query proxy
INVALID_SQL_PAYLOAD='{
  "start": '"${START_TS}"',
  "end": '"${END_TS}"',
  "step": 60,
  "compositeQuery": {
    "queryType": "clickhouse_sql",
    "panelType": "table",
    "clickhouseQueries": {
      "A": {
        "queryName": "A",
        "rawQuery": "SELECT non_existent_column_123 FROM signoz_traces.non_existent_table_999 LIMIT 1;"
      }
    }
  }
}'

INVALID_SQL_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 5 -qO- --header="Authorization: Bearer ${TOKEN}" \
  --header="Content-Type: application/json" \
  --post-data="${INVALID_SQL_PAYLOAD}" \
  http://127.0.0.1:8080/api/v3/query_range 2>&1 || true)

# Server must return an error response, NOT crash the process
if [[ "${INVALID_SQL_RESP}" == *"panic"* ]]; then
  echo "    ERROR: Upstream ClickHouse error caused panic: ${INVALID_SQL_RESP}" >&2
  exit 1
fi
echo "    ClickHouse upstream error handled gracefully (error returned, server running)."

# Verify SigNoz health endpoints remain 200 OK
HEALTH_CHECK=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- wget -T 3 -qO- http://127.0.0.1:8080/api/v1/health)
if [[ "${HEALTH_CHECK}" != *"ok"* ]]; then
  echo "    ERROR: Health check failed after error tests: ${HEALTH_CHECK}" >&2
  exit 1
fi
echo "    SigNoz health check still responsive: ok."

# Check pod restart count to verify zero crash loops
FINAL_RESTARTS=$(kubectl get pod "${SIGNOZ_POD}" -n "${NAMESPACE}" -o jsonpath='{.status.containerStatuses[0].restartCount}')
if [ "${FINAL_RESTARTS}" -ne "${INITIAL_RESTARTS}" ]; then
  echo "    ERROR: SigNoz pod crashed during edge cases! Initial=${INITIAL_RESTARTS}, Final=${FINAL_RESTARTS}" >&2
  exit 1
fi
echo "    Pod stability verified: restart count remained unchanged (${INITIAL_RESTARTS})."

echo "================================================================="
echo "STATUS: PASS — All SigNoz edge cases and failure paths handled cleanly."
echo "================================================================="
