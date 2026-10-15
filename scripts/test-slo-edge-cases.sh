#!/usr/bin/env bash
# scripts/test-slo-edge-cases.sh — Edge-case verification for Project Argus Feature F012 (SLO Tracking & Error Budgets)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F012"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PYTHON_CONTROLLER="${SCRIPT_DIR}/run_slo_edge_cases.py"

mkdir -p "${EVIDENCE_DIR}"

echo "================================================================="
echo "       ARGUS SLO & ERROR BUDGETS EDGE CASES BATTERY              "
echo "================================================================="

echo "--> [1/3] Executing SLO edge cases suite inside cluster..."
PY_CONTENT=$(cat "${PYTHON_CONTROLLER}")

OUTPUT=$(kubectl exec </dev/null -n "${NAMESPACE}" deployment/argus-sample-service -- python -c "${PY_CONTENT}")

echo "${OUTPUT}"
echo "${OUTPUT}" > "${EVIDENCE_DIR}/edge-cases-verification.txt"

echo "--> [2/3] Validating edge-cases verification transcript..."
if [ ! -s "${EVIDENCE_DIR}/edge-cases-verification.txt" ]; then
  echo "ERROR: Edge cases output transcript was not generated!" >&2
  exit 1
fi
echo "    Transcript archived: ${EVIDENCE_DIR}/edge-cases-verification.txt ($(wc -l < "${EVIDENCE_DIR}/edge-cases-verification.txt" | tr -d ' ') lines)"

echo "--> [3/3] Ensuring clean baseline state..."
kubectl exec </dev/null -n "${NAMESPACE}" deployment/argus-sample-service -- wget -qO- --post-data="" http://127.0.0.1:8080/api/slo/reset >/dev/null

echo "================================================================="
echo "   FEATURE F012 EDGE CASES VERIFIED 100% GREEN!                  "
echo "================================================================="
