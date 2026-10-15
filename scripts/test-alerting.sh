#!/usr/bin/env bash
# scripts/test-alerting.sh — End-to-end verification of Project Argus Alerting & Monitors
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F011"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PYTHON_CONTROLLER="${SCRIPT_DIR}/run_alert_e2e.py"

mkdir -p "${EVIDENCE_DIR}"

echo "================================================================="
echo "       ARGUS ALERTING & MONITORS END-TO-END VERIFICATION         "
echo "================================================================="

# 1. Apply Declarative Rule Manifests
echo "--> [1/4] Applying declarative alert rules via apply-rules.sh..."
"${ROOT_DIR}/deploy/alerting/apply-rules.sh"

# 2. Execute E2E Lifecycle Controller inside cluster
echo "--> [2/4] Running E2E alert lifecycle test (breach -> firing -> dedup -> recovery)..."
PY_CONTENT=$(cat "${PYTHON_CONTROLLER}")

OUTPUT=$(kubectl exec </dev/null -n "${NAMESPACE}" deployment/argus-sample-service -- python -c "${PY_CONTENT}")

echo "${OUTPUT}" | while IFS= read -r line; do
  case "${line}" in
    RESULT_FIRING:*)
      echo "${line#RESULT_FIRING:}" | jq . > "${EVIDENCE_DIR}/alert-firing-proof.json"
      ;;
    RESULT_DEDUP:*)
      echo "${line#RESULT_DEDUP:}" | jq . > "${EVIDENCE_DIR}/alert-dedup-proof.json"
      ;;
    RESULT_RESOLVED:*)
      echo "${line#RESULT_RESOLVED:}" | jq . > "${EVIDENCE_DIR}/alert-resolved-proof.json"
      ;;
    *)
      echo "${line}"
      ;;
  esac
done

echo "--> [3/4] Verifying generated evidence artifacts..."
for artifact in alert-firing-proof.json alert-dedup-proof.json alert-resolved-proof.json; do
  if [ ! -s "${EVIDENCE_DIR}/${artifact}" ]; then
    echo "ERROR: Expected evidence artifact ${artifact} was not produced or is empty!" >&2
    exit 1
  fi
  echo "    Archived: ${EVIDENCE_DIR}/${artifact}"
done

# 4. Restore Baseline Declarative Rules
echo "--> [4/4] Restoring baseline declarative alert rules..."
"${ROOT_DIR}/deploy/alerting/apply-rules.sh" >/dev/null
echo "    Baseline rules successfully restored."

echo "================================================================="
echo "   FEATURE F011 ALERTING & MONITORS VERIFIED 100% GREEN!         "
echo "================================================================="
