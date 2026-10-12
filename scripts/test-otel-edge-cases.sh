#!/usr/bin/env bash
# scripts/test-otel-edge-cases.sh — Edge cases and resilience tests for OTel Collector pipeline
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PASSED_COUNT=0
FAILED_COUNT=0

echo "================================================================="
echo "     OPENTELEMETRY COLLECTOR EDGE CASES & RESILIENCE BATTERY     "
echo "================================================================="

# 1. Edge Case: Malformed OTLP Payloads Rejected Cleanly (HTTP 400, no crash)
echo "--> Test 1: Malformed OTLP payloads rejected with HTTP 400 without collector failure..."
HTTP_CODE=$(kubectl exec -n "${NAMESPACE}" deploy/argus-s3 -- curl -s -o /dev/null -w "%{http_code}" -X POST \
  "http://argus-gateway-collector.argus-system.svc.cluster.local:4318/v1/traces" \
  -H "Content-Type: application/json" \
  -d '{"invalid_syntax": not_valid_json}' || echo "000")

echo "    Response code for malformed trace JSON: ${HTTP_CODE}"
if [ "${HTTP_CODE}" == "400" ]; then
  echo "    PASS: Gateway correctly rejected malformed payload with HTTP 400."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Expected HTTP 400, got ${HTTP_CODE}." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

GATEWAY_READY=$(kubectl get deploy argus-gateway-collector -n "${NAMESPACE}" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
if [ "${GATEWAY_READY}" -ge 1 ]; then
  echo "    PASS: Gateway deployment remained healthy and resilient after malformed input."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Gateway deployment crashed after malformed input." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# 2. Edge Case: Node DaemonSet Pod Kill & Clean Recovery
echo "--> Test 2: Node DaemonSet pod kill and clean recovery without filelock crash..."
DS_POD=$(kubectl get pod -l app.kubernetes.io/name=argus-node-collector-collector -n "${NAMESPACE}" -o jsonpath='{.items[0].metadata.name}')
echo "    Simulating node agent crash: deleting pod '${DS_POD}'..."
kubectl delete pod "${DS_POD}" -n "${NAMESPACE}" --wait=true

echo "    Awaiting replacement daemonset pod rollout..."
kubectl rollout status daemonset/argus-node-collector-collector -n "${NAMESPACE}" --timeout=120s

NEW_DS_POD=$(kubectl get pod -l app.kubernetes.io/name=argus-node-collector-collector -n "${NAMESPACE}" -o jsonpath='{.items[0].metadata.name}')
NEW_POD_STATUS=$(kubectl get pod "${NEW_DS_POD}" -n "${NAMESPACE}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')

if [ "${NEW_POD_STATUS}" == "True" ]; then
  echo "    PASS: Node DaemonSet spawned new pod '${NEW_DS_POD}' and reached Ready without crash loops."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Node DaemonSet pod failed to recover cleanly." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# 3. Edge Case: Gateway Pod Restart & Resumed Ingestion
echo "--> Test 3: Gateway deployment rollout restart preserves pipeline connectivity..."
kubectl rollout restart deployment/argus-gateway-collector -n "${NAMESPACE}"
kubectl rollout status deployment/argus-gateway-collector -n "${NAMESPACE}" --timeout=120s

CANARY_PING="000"
for i in $(seq 1 15); do
  CANARY_PING=$(kubectl exec -n "${NAMESPACE}" deploy/argus-s3 -- curl -s -o /dev/null -w "%{http_code}" -X POST \
    "http://argus-gateway-collector.argus-system.svc.cluster.local:4318/v1/traces" \
    -H "Content-Type: application/json" \
    -d '{"resourceSpans":[]}' 2>/dev/null || echo "000")
  if [ "${CANARY_PING}" == "200" ]; then
    break
  fi
  sleep 1
done

echo "    Response code on fresh gateway after restart: ${CANARY_PING}"
if [ "${CANARY_PING}" == "200" ]; then
  echo "    PASS: Gateway accepted OTLP traffic immediately after restart."
  PASSED_COUNT=$((PASSED_COUNT + 1))
else
  echo "    FAIL: Gateway did not resume traffic after restart (got ${CANARY_PING})." >&2
  FAILED_COUNT=$((FAILED_COUNT + 1))
fi

# Summary
echo "================================================================="
echo "Edge case results: ${PASSED_COUNT} passed, ${FAILED_COUNT} failed."
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "STATUS: FAIL" >&2
  exit 1
else
  echo "STATUS: PASS — All OpenTelemetry Collector edge cases passed."
  exit 0
fi
