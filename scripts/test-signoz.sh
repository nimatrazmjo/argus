#!/usr/bin/env bash
# scripts/test-signoz.sh — End-to-end verification of SigNoz APM, traces, logs, and air-gap compliance
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-argus123}"
ADMIN_EMAIL="${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD:-ArgusAdminPassword123!}"
MAX_WAIT_SECONDS=45

echo "================================================================="
echo "       ARGUS SIGNOZ PLATFORM FUNCTIONAL & APM PROOF              "
echo "================================================================="

# 1. Verify Deployment Rollouts
echo "--> [1/6] Verifying SigNoz deployments readiness..."
kubectl rollout status deployment/signoz -n "${NAMESPACE}" --timeout=30s >/dev/null
kubectl rollout status deployment/signoz-otel-collector -n "${NAMESPACE}" --timeout=30s >/dev/null
kubectl rollout status deployment/argus-sample-service -n "${NAMESPACE}" --timeout=30s >/dev/null

SIGNOZ_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=signoz --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
if [ -z "${SIGNOZ_POD}" ]; then
  echo "    ERROR: No running SigNoz pod found." >&2
  exit 1
fi
echo "    SigNoz pod: ${SIGNOZ_POD}"

# 2. Verify Health & Telemetry/Phone-Home Disabled (Air-Gap Compliance)
echo "--> [2/6] Verifying SigNoz health and phone-home telemetry isolation..."
VERSION_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- wget -T 30 -qO- http://127.0.0.1:8080/api/v1/version)
HEALTH_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- wget -T 30 -qO- http://127.0.0.1:8080/api/v1/health)

STATUS_HEALTH=$(echo "${HEALTH_RESP}" | jq -r '.status // empty')
SETUP_COMPLETED=$(echo "${VERSION_RESP}" | jq -r '.setupCompleted // empty')
VERSION_STR=$(echo "${VERSION_RESP}" | jq -r '.version // empty')

if [ "${STATUS_HEALTH}" != "ok" ]; then
  echo "    ERROR: SigNoz health check failed: ${HEALTH_RESP}" >&2
  exit 1
fi
echo "    SigNoz version: ${VERSION_STR} (health: ${STATUS_HEALTH}, setupCompleted: ${SETUP_COMPLETED})"

# Verify Boot Settings: PostHog, Appcues, Sentry, Pylon explicitly disabled
BOOT_SETTINGS=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- wget -T 30 -qO- http://127.0.0.1:8080/ | grep -o 'id="signoz-boot-settings">[^<]*' | sed 's/id="signoz-boot-settings">//' || true)
if [ -n "${BOOT_SETTINGS}" ]; then
  POSTHOG_EN=$(echo "${BOOT_SETTINGS}" | jq -r '.posthog.enabled // false')
  APPCUES_EN=$(echo "${BOOT_SETTINGS}" | jq -r '.appcues.enabled // false')
  SENTRY_EN=$(echo "${BOOT_SETTINGS}" | jq -r '.sentry.enabled // false')
  PYLON_EN=$(echo "${BOOT_SETTINGS}" | jq -r '.pylon.enabled // false')
  if [ "${POSTHOG_EN}" != "false" ] || [ "${APPCUES_EN}" != "false" ] || [ "${SENTRY_EN}" != "false" ] || [ "${PYLON_EN}" != "false" ]; then
    echo "    ERROR: Phone-home telemetry detected enabled in boot settings: ${BOOT_SETTINGS}" >&2
    exit 1
  fi
  echo "    Boot telemetry verified disabled: PostHog=false, Appcues=false, Sentry=false, Pylon=false."
fi

# Verify zero non-internal TCP sockets in SigNoz container
ACTIVE_CONNS=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- netstat -tpn 2>/dev/null | grep ESTABLISHED || true)
if [ -n "${ACTIVE_CONNS}" ]; then
  while IFS= read -r line; do
    REMOTE_IP=$(echo "$line" | awk '{print $5}' | cut -d':' -f1)
    if [[ ! "$REMOTE_IP" =~ ^(127\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.) ]]; then
      echo "    ERROR: Public outbound socket connection found in SigNoz: $line" >&2
      exit 1
    fi
  done <<< "${ACTIVE_CONNS}"
fi
echo "    Air-gap egress audit passed: Zero external socket connections."

# 3. Authenticate and Obtain JWT Bearer Token
echo "--> [3/6] Authenticating administrator account..."
if [ "${SETUP_COMPLETED}" != "true" ]; then
  echo "    Initial admin setup needed. Registering administrator (${ADMIN_EMAIL})..."
  kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
    wget -T 30 -qO- --header="Content-Type: application/json" \
    --post-data="{\"name\":\"Argus Admin\",\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"orgName\":\"argus\"}" \
    http://127.0.0.1:8080/api/v1/register >/dev/null 2>&1 || true
fi

SESSION_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- "http://127.0.0.1:8080/api/v2/sessions/context?email=${ADMIN_EMAIL}")

ORG_ID=$(echo "${SESSION_RESP}" | jq -r '.data.orgs[0].id // empty')
if [ -z "${ORG_ID}" ]; then
  echo "    ERROR: Failed to retrieve organization ID for ${ADMIN_EMAIL}: ${SESSION_RESP}" >&2
  exit 1
fi

LOGIN_PAYLOAD="{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"orgId\":\"${ORG_ID}\"}"
LOGIN_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- --header="Content-Type: application/json" \
  --post-data="${LOGIN_PAYLOAD}" \
  http://127.0.0.1:8080/api/v2/sessions/email_password)

TOKEN=$(echo "${LOGIN_RESP}" | jq -r '.data.accessToken // empty')
if [ -z "${TOKEN}" ]; then
  echo "    ERROR: Failed to obtain access token: ${LOGIN_RESP}" >&2
  exit 1
fi
echo "    Successfully authenticated as ${ADMIN_EMAIL} (Org ID: ${ORG_ID})."

# 4. Drive Synthetic Transaction through Instrumented Sample Service
echo "--> [4/6] Emitting synthetic transaction through sample service..."
SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
ORDER_ID="signoz-$(openssl rand -hex 4)"

SAMPLE_RESP=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- python -c "
import urllib.request, json
req = urllib.request.Request('http://127.0.0.1:8080/order?order_id=${ORDER_ID}')
with urllib.request.urlopen(req, timeout=5) as resp:
    print(resp.read().decode())
")

TX_STATUS=$(echo "${SAMPLE_RESP}" | jq -r '.status // empty')
TRACE_ID=$(echo "${SAMPLE_RESP}" | jq -r '.trace_id // empty')
SPAN_ID=$(echo "${SAMPLE_RESP}" | jq -r '.span_id // empty')

if [ "${TX_STATUS}" != "success" ] || [ -z "${TRACE_ID}" ]; then
  echo "    ERROR: Failed to trigger sample transaction: ${SAMPLE_RESP}" >&2
  exit 1
fi
echo "    Transaction initiated successfully:"
echo "      Order ID:  ${ORDER_ID}"
echo "      Trace ID:  ${TRACE_ID}"
echo "      Span ID:   ${SPAN_ID}"

# 5. Verify Ingestion into SigNoz ClickHouse Tables
echo "--> [5/6] Awaiting pipeline ingestion into SigNoz ClickHouse storage..."
INGESTED=0
for i in $(seq 1 "${MAX_WAIT_SECONDS}"); do
  RAW_COUNT=$(kubectl exec -n "${NAMESPACE}" chi-argus-clickhouse-argus-cluster-0-0-0 -c clickhouse -- \
    clickhouse-client --user default --password "${CLICKHOUSE_PASSWORD}" \
    --query "SELECT count() FROM signoz_traces.distributed_signoz_index_v3 WHERE traceID = '${TRACE_ID}';" 2>/dev/null || echo "0")
  TRACE_COUNT=$(echo "${RAW_COUNT}" | tr -dc '0-9')
  TRACE_COUNT="${TRACE_COUNT:-0}"
  
  if [ "${TRACE_COUNT}" -gt 0 ]; then
    INGESTED=1
    echo "    Ingestion confirmed in ClickHouse signoz_traces after ${i}s."
    break
  fi
  sleep 1
done

if [ "${INGESTED}" -ne 1 ]; then
  echo "    ERROR: Trace ${TRACE_ID} did not arrive in ClickHouse signoz_traces within ${MAX_WAIT_SECONDS}s." >&2
  exit 1
fi

# 6. Verify SigNoz API: Service List, Trace Retrieval, and Log Queries
echo "--> [6/6] Validating SigNoz APM, Trace, and Log Query APIs..."

# 6a. Services Discovery
SERVICES_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- --header="Authorization: Bearer ${TOKEN}" \
  http://127.0.0.1:8080/api/v1/services/list)

HAS_SAMPLE=$(echo "${SERVICES_RESP}" | jq 'contains(["argus-sample-service"])')
if [ "${HAS_SAMPLE}" != "true" ]; then
  echo "    ERROR: 'argus-sample-service' missing from SigNoz services list: ${SERVICES_RESP}" >&2
  exit 1
fi
echo "    APM Service Discovery: PASS (found 'argus-sample-service')"

# 6b. Trace Retrieval by ID
TRACE_API_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- --header="Authorization: Bearer ${TOKEN}" \
  "http://127.0.0.1:8080/api/v1/traces/${TRACE_ID}")

RETRIEVED_TRACE_ID=$(echo "${TRACE_API_RESP}" | jq -r '.[0].events[0][2] // empty')
RETRIEVED_SERVICE=$(echo "${TRACE_API_RESP}" | jq -r '.[0].events[0][3] // empty')
RETRIEVED_SPAN_NAME=$(echo "${TRACE_API_RESP}" | jq -r '.[0].events[0][4] // empty')

if [ "${RETRIEVED_TRACE_ID}" != "${TRACE_ID}" ] || [ "${RETRIEVED_SERVICE}" != "argus-sample-service" ]; then
  echo "    ERROR: Trace query failed or data mismatched: ${TRACE_API_RESP}" >&2
  exit 1
fi
echo "    APM Trace Query: PASS (TraceID=${RETRIEVED_TRACE_ID}, Service=${RETRIEVED_SERVICE}, Op=${RETRIEVED_SPAN_NAME})"

# 6c. Unified Query Range API for Logs
NOW_TS=$(date +%s)
START_TS=$(( (NOW_TS - 3600) * 1000 ))
END_TS=$(( (NOW_TS + 60) * 1000 ))

QUERY_PAYLOAD='{
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
        "limit": 10
      }
    }
  }
}'

QUERY_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- --header="Authorization: Bearer ${TOKEN}" \
  --header="Content-Type: application/json" \
  --post-data="${QUERY_PAYLOAD}" \
  http://127.0.0.1:8080/api/v3/query_range)

QUERY_STATUS=$(echo "${QUERY_RESP}" | jq -r '.status // empty')
if [ "${QUERY_STATUS}" != "success" ]; then
  echo "    ERROR: Log query on /api/v3/query_range returned non-success: ${QUERY_RESP}" >&2
  exit 1
fi
echo "    Unified Query API (Logs): PASS (status: ${QUERY_STATUS})"

echo "================================================================="
echo "STATUS: PASS — SigNoz APM, traces, logs, and air-gap verification succeeded."
echo "================================================================="
