#!/usr/bin/env bash
# scripts/test-nl-query.sh — NL Query & Incident Summarization Verification (F021)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F021"

echo "================================================================="
echo "   ARGUS NL QUERY & INCIDENT SUMMARIZATION PROOF (F021)          "
echo "================================================================="

echo "--> [1/4] Ensuring AIOps LLM Service infrastructure is ready via apply-llm.sh..."
"${ROOT_DIR}/deploy/llm/apply-llm.sh"

JWT_SECRET_VAL="$(kubectl get secret argus-sso-secret -n "${NAMESPACE}" -o jsonpath='{.data.jwt-secret}' | base64 -d)"

SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-sample-service --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${SAMPLE_POD}" ]; then
  SAMPLE_POD=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=argus-aiops-llm --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}')
fi

mkdir -p "${EVIDENCE_DIR}"

echo "--> [2/4] Executing NL Query & Incident Summarization E2E suite via cluster pod..."
kubectl exec -n "${NAMESPACE}" "${SAMPLE_POD}" -- env \
  LLM_URL="http://argus-aiops-llm.${NAMESPACE}.svc.cluster.local:9098" \
  JWT_SECRET="${JWT_SECRET_VAL}" \
  EVIDENCE_DIR="/tmp/evidence-f021" \
  python -c "
import os
$(cat "${SCRIPT_DIR}/run_nl_query_e2e.py")
"

echo "--> [3/4] Collecting evidence into ${EVIDENCE_DIR}..."
cat "${ROOT_DIR}/deploy/llm/aiops-llm-workloads.yaml" > "${EVIDENCE_DIR}/aiops-llm-workloads.yaml"

kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f021/nl-to-sql-benchmarks.json" "${EVIDENCE_DIR}/nl-to-sql-benchmarks.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f021/govcloud-bedrock-egress-proof.json" "${EVIDENCE_DIR}/govcloud-bedrock-egress-proof.json"
kubectl cp -n "${NAMESPACE}" "${SAMPLE_POD}:/tmp/evidence-f021/incident-summary-output.json" "${EVIDENCE_DIR}/incident-summary-output.json"

echo "--> [4/4] Validating evidence artifacts in ${EVIDENCE_DIR}..."
for art in nl-to-sql-benchmarks.json govcloud-bedrock-egress-proof.json incident-summary-output.json aiops-llm-workloads.yaml; do
  if [ -s "${EVIDENCE_DIR}/${art}" ]; then
    echo "    Verified artifact [OK]: ${art} ($(wc -c < "${EVIDENCE_DIR}/${art}" | tr -d ' ') bytes)"
  else
    echo "    ERROR: ${art} missing or empty!" >&2
    exit 1
  fi
done

echo "================================================================="
echo "   FEATURE F021 NL QUERY & SUMMARIZATION VERIFIED 100% GREEN!    "
echo "================================================================="
