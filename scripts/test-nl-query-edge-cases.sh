#!/usr/bin/env bash
# scripts/test-nl-query-edge-cases.sh — NL Query Edge Cases & Safety Guardrails Battery (F021)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F021"

echo "================================================================="
echo "   ARGUS NL QUERY & LLM EDGE CASES & SAFETY BATTERY (F021)       "
echo "================================================================="

JWT_SECRET_VAL="$(kubectl get secret argus-sso-secret -n "${NAMESPACE}" -o jsonpath='{.data.jwt-secret}' | base64 -d)"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-aiops-llm --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [1/3] Executing NL Query Edge Cases controller via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env \
  LLM_URL="http://argus-aiops-llm.${NAMESPACE}.svc.cluster.local:9098" \
  JWT_SECRET="${JWT_SECRET_VAL}" \
  EVIDENCE_DIR="/tmp/evidence-f021" \
  python -c "
import os
$(cat "${SCRIPT_DIR}/run_nl_query_edge_cases.py")
"

echo "--> [2/3] Collecting edge cases evidence into ${EVIDENCE_DIR}..."
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f021/nl-llm-edge-cases-report.json" "${EVIDENCE_DIR}/nl-llm-edge-cases-report.json"

echo "--> [3/3] Validating edge cases evidence artifacts..."
if [ -s "${EVIDENCE_DIR}/nl-llm-edge-cases-report.json" ]; then
  echo "    Verified artifact [OK]: nl-llm-edge-cases-report.json ($(wc -c < "${EVIDENCE_DIR}/nl-llm-edge-cases-report.json" | tr -d ' ') bytes)"
else
  echo "    ERROR: nl-llm-edge-cases-report.json missing or empty!" >&2
  exit 1
fi

echo "================================================================="
echo "   FEATURE F021 NL & LLM EDGE CASES VERIFIED 100% GREEN!         "
echo "================================================================="
