#!/usr/bin/env bash
# scripts/test-auto-instrumentation.sh — Functional & E2E verification of Zero-Code Auto-Instrumentation
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
CLICKHOUSE_PASSWORD="${ARGUS_CLICKHOUSE_PASSWORD:-argus123}"
ADMIN_EMAIL="${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD:-ArgusAdminPassword123!}"
EVIDENCE_DIR=".harness/evidence/F007"
MAX_WAIT_SECONDS=45

mkdir -p "${EVIDENCE_DIR}"

echo "================================================================="
echo "  ARGUS ZERO-CODE AUTO-INSTRUMENTATION FUNCTIONAL VERIFICATION  "
echo "================================================================="

# 1. Verify Instrumentation CR
echo "--> [1/7] Validating Instrumentation Custom Resource..."
if ! kubectl get instrumentation argus-instrumentation -n "${NAMESPACE}" >/dev/null 2>&1; then
  echo "    ERROR: Instrumentation CR 'argus-instrumentation' not found in namespace '${NAMESPACE}'." >&2
  exit 1
fi

CR_SPEC=$(kubectl get instrumentation argus-instrumentation -n "${NAMESPACE}" -o json)
ENDPOINT=$(echo "${CR_SPEC}" | jq -r '.spec.exporter.endpoint // empty')
PY_IMG=$(echo "${CR_SPEC}" | jq -r '.spec.python.image // empty')

echo "    Instrumentation endpoint: ${ENDPOINT}"
echo "    Python auto-agent image:  ${PY_IMG}"

if [[ "${PY_IMG}" != *"localhost:5001/argus/"* ]]; then
  echo "    ERROR: Python auto-agent image must resolve from local air-gapped mirror (localhost:5001/argus/*)." >&2
  exit 1
fi

# 2. Deploy Zero-Code Sample Application
echo "--> [2/7] Ensuring zero-code sample application is deployed..."
kubectl apply -f deploy/sample-app/auto-instrumented-service.yaml
kubectl rollout status deployment/argus-auto-service -n "${NAMESPACE}" --timeout=60s

AUTO_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-auto-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
if [ -z "${AUTO_POD}" ]; then
  echo "    ERROR: No running pod found for argus-auto-service." >&2
  exit 1
fi
echo "    Running pod identified: ${AUTO_POD}"

# 3. Verify Mutating Webhook Injection (Init container, Env vars, Volumes)
echo "--> [3/7] Verifying mutating webhook injection into pod spec..."
POD_JSON=$(kubectl get pod -n "${NAMESPACE}" "${AUTO_POD}" -o json)
echo "${POD_JSON}" | jq '{name: .metadata.name, initContainers: [(.spec.initContainers // [])[].name], env: [(.spec.containers[0].env // [])[].name]}' > "${EVIDENCE_DIR}/injected-pod-spec.json"

HAS_INIT=$(echo "${POD_JSON}" | jq '(.spec.initContainers // []) | any(.name == "opentelemetry-auto-instrumentation-python")')
HAS_PYTHONPATH=$(echo "${POD_JSON}" | jq '(.spec.containers[0].env // []) | any(.name == "PYTHONPATH")')
HAS_ENDPOINT_ENV=$(echo "${POD_JSON}" | jq '(.spec.containers[0].env // []) | any(.name == "OTEL_EXPORTER_OTLP_ENDPOINT")')

if [ "${HAS_INIT}" != "true" ] || [ "${HAS_PYTHONPATH}" != "true" ] || [ "${HAS_ENDPOINT_ENV}" != "true" ]; then
  echo "    ERROR: Mutating webhook injection incomplete." >&2
  echo "      Has init container: ${HAS_INIT}" >&2
  echo "      Has PYTHONPATH:     ${HAS_PYTHONPATH}" >&2
  echo "      Has OTLP endpoint:  ${HAS_ENDPOINT_ENV}" >&2
  exit 1
fi
echo "    Webhook injection confirmed: init-container, PYTHONPATH, and exporter env present."

# 4. Trigger Synthetic HTTP Transactions
echo "--> [4/7] Generating synthetic transaction against zero-code service..."
ORDER_ID="auto-$(openssl rand -hex 4)"
SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')

TX_RESP=$(kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- wget -qO- \
  "http://argus-auto-service.${NAMESPACE}:8080/api/order?order_id=${ORDER_ID}")

echo "    Response: ${TX_RESP}"
TX_ORDER=$(echo "${TX_RESP}" | jq -r '.order_id // empty')
TX_STATUS=$(echo "${TX_RESP}" | jq -r '.status // empty')

if [ "${TX_STATUS}" != "PROCESSED" ] || [ "${TX_ORDER}" != "${ORDER_ID}" ]; then
  echo "    ERROR: Transaction failed: ${TX_RESP}" >&2
  exit 1
fi
echo "    Transaction processed successfully with order ID: ${ORDER_ID}"

# 5. Verify ClickHouse Ingestion for Auto-Instrumented Spans
echo "--> [5/7] Verifying auto-instrumented spans in ClickHouse storage..."
CLICKHOUSE_POD="chi-argus-clickhouse-argus-cluster-0-0-0"
INGESTED=0

for i in $(seq 1 "${MAX_WAIT_SECONDS}"); do
  SPAN_COUNT=$(kubectl exec -n "${NAMESPACE}" "${CLICKHOUSE_POD}" -c clickhouse -- \
    clickhouse-client --user default --password "${CLICKHOUSE_PASSWORD}" \
    --query "SELECT count() FROM signoz_traces.signoz_index_v3 WHERE serviceName = 'argus-auto-service' AND name = 'GET /api/order';" 2>/dev/null || echo "0")
  
  if [ "${SPAN_COUNT}" -gt 0 ]; then
    INGESTED=1
    echo "    Ingestion confirmed: found ${SPAN_COUNT} spans for 'argus-auto-service' after ${i}s."
    break
  fi
  sleep 1
done

if [ "${INGESTED}" -ne 1 ]; then
  echo "    ERROR: Spans for argus-auto-service did not arrive in ClickHouse within ${MAX_WAIT_SECONDS}s." >&2
  exit 1
fi

# Fetch and store trace record
AUTO_SPANS=$(kubectl exec -n "${NAMESPACE}" "${CLICKHOUSE_POD}" -c clickhouse -- \
  clickhouse-client --user default --password "${CLICKHOUSE_PASSWORD}" \
  --query "SELECT timestamp, traceID, spanID, serviceName, name, kind, responseStatusCode FROM signoz_traces.signoz_index_v3 WHERE serviceName = 'argus-auto-service' ORDER BY timestamp DESC LIMIT 5 FORMAT JSONEachRow;")

echo "${AUTO_SPANS}" > "${EVIDENCE_DIR}/clickhouse-auto-spans.json"
CAPTURED_TRACE_ID=$(echo "${AUTO_SPANS}" | head -n 1 | jq -r '.traceID // empty')
echo "    Captured Trace ID: ${CAPTURED_TRACE_ID}"

# 6. Verify SigNoz APM Discovery & Service Listing
echo "--> [6/7] Validating SigNoz APM service discovery..."
SIGNOZ_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=signoz -o jsonpath='{.items[0].metadata.name}')

SESSION_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 10 -qO- "http://127.0.0.1:8080/api/v2/sessions/context?email=${ADMIN_EMAIL}")

ORG_ID=$(echo "${SESSION_RESP}" | jq -r '.data.orgs[0].id // empty')
LOGIN_PAYLOAD="{\"email\":\"${ADMIN_EMAIL}\",\"password\":\"${ADMIN_PASSWORD}\",\"orgId\":\"${ORG_ID}\"}"

LOGIN_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 10 -qO- --header="Content-Type: application/json" \
  --post-data="${LOGIN_PAYLOAD}" \
  http://127.0.0.1:8080/api/v2/sessions/email_password)

TOKEN=$(echo "${LOGIN_RESP}" | jq -r '.data.accessToken // empty')
if [ -z "${TOKEN}" ]; then
  echo "    ERROR: Failed to authenticate to SigNoz query-service." >&2
  exit 1
fi

SERVICES_LIST=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- --header="Authorization: Bearer ${TOKEN}" \
  http://127.0.0.1:8080/api/v1/services/list)

echo "${SERVICES_LIST}" > "${EVIDENCE_DIR}/signoz-services-list.json"
HAS_AUTO_SERVICE=$(echo "${SERVICES_LIST}" | jq 'contains(["argus-auto-service"])')

if [ "${HAS_AUTO_SERVICE}" != "true" ]; then
  echo "    ERROR: 'argus-auto-service' not found in SigNoz services list: ${SERVICES_LIST}" >&2
  exit 1
fi
echo "    SigNoz APM Discovery: PASS (found 'argus-auto-service' in services catalog)"

# 7. Verify Trace Retrieval from SigNoz API
echo "--> [7/7] Retrieving trace from SigNoz API by Trace ID..."
TRACE_RESP=$(kubectl exec -n "${NAMESPACE}" "${SIGNOZ_POD}" -- \
  wget -T 30 -qO- --header="Authorization: Bearer ${TOKEN}" \
  "http://127.0.0.1:8080/api/v1/traces/${CAPTURED_TRACE_ID}")

echo "${TRACE_RESP}" > "${EVIDENCE_DIR}/signoz-auto-trace.json"
RETRIEVED_SERVICE=$(echo "${TRACE_RESP}" | jq -r '.[0].events[0][3] // empty')

if [ "${RETRIEVED_SERVICE}" != "argus-auto-service" ]; then
  echo "    WARN: Direct trace events list format varied, checking raw JSON response presence..."
  if ! echo "${TRACE_RESP}" | grep -q "argus-auto-service"; then
    echo "    ERROR: Trace payload does not contain argus-auto-service: ${TRACE_RESP}" >&2
    exit 1
  fi
fi
echo "    SigNoz Trace Retrieval: PASS"

echo "================================================================="
echo "STATUS: PASS — Zero-Code Auto-Instrumentation verified E2E."
echo "================================================================="
exit 0
