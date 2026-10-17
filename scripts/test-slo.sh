#!/usr/bin/env bash
# scripts/test-slo.sh — End-to-end verification of Project Argus Feature F012 (SLO Tracking & Error Budgets)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F012"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
PYTHON_CONTROLLER="${SCRIPT_DIR}/run_slo_e2e.py"

mkdir -p "${EVIDENCE_DIR}"

echo "================================================================="
echo "       ARGUS SLO TRACKING & ERROR BUDGETS VERIFICATION (F012)    "
echo "================================================================="

# 1. Apply Declarative OpenSLO Rules to SigNoz Ruler
echo "--> [1/4] Synchronizing declarative SLO alert rules via apply-slo.sh..."
"${ROOT_DIR}/deploy/slo/apply-slo.sh"

cp "${ROOT_DIR}/deploy/slo/slo-definition.json" "${EVIDENCE_DIR}/slo-definition.json"
echo "    Archived OpenSLO manifest to ${EVIDENCE_DIR}/slo-definition.json"

# 2. Execute E2E Controller inside cluster
echo "--> [2/4] Executing E2E SLO burndown controller inside cluster..."
PY_CONTENT=$(cat "${PYTHON_CONTROLLER}")
SIGNOZ_ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD:-ArgusAdminPassword123!}"

OUTPUT=$(kubectl exec </dev/null -n "${NAMESPACE}" deployment/argus-sample-service -- env SIGNOZ_ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD}" python -c "${PY_CONTENT}")

echo "${OUTPUT}" | while IFS= read -r line; do
  case "${line}" in
    SLO_BASELINE:*)
      echo "${line#SLO_BASELINE:}" | jq . > "${EVIDENCE_DIR}/slo-status-baseline.json"
      ;;
    SLO_BURNED:*)
      echo "${line#SLO_BURNED:}" | jq . > "${EVIDENCE_DIR}/slo-status-post-burn.json"
      ;;
    SLO_HTML_DASHBOARD:*)
      echo "${line#SLO_HTML_DASHBOARD:}" | jq -r '.content' > "${EVIDENCE_DIR}/slo-dashboard-proof.html"
      ;;
    SLO_RULES_SYNCED:*)
      echo "${line#SLO_RULES_SYNCED:}" | jq . > "${EVIDENCE_DIR}/slo-alert-rules-synced.json"
      ;;
    *)
      echo "${line}"
      ;;
  esac
done

# 3. Verify Artifact Integrity
echo "--> [3/4] Validating generated evidence artifacts in ${EVIDENCE_DIR}..."
EXPECTED_ARTIFACTS=(
  "slo-definition.json"
  "slo-status-baseline.json"
  "slo-status-post-burn.json"
  "slo-dashboard-proof.html"
  "slo-alert-rules-synced.json"
)

for artifact in "${EXPECTED_ARTIFACTS[@]}"; do
  file_path="${EVIDENCE_DIR}/${artifact}"
  if [ ! -s "${file_path}" ]; then
    echo "ERROR: Expected evidence artifact ${artifact} is missing or empty!" >&2
    exit 1
  fi
  echo "    Verified artifact [OK]: ${artifact} ($(wc -c < "${file_path}" | tr -d ' ') bytes)"
done

# 4. Clean reset
echo "--> [4/4] Resetting SLO tracker counters to baseline..."
kubectl exec </dev/null -n "${NAMESPACE}" deployment/argus-sample-service -- sh -c 'wget -qO- --header="Authorization: Bearer ${SAMPLE_APP_API_TOKEN}" --post-data="" http://127.0.0.1:8080/api/slo/reset >/dev/null'
echo "    SLO tracker successfully reset."

echo "================================================================="
echo "   FEATURE F012 SLO TRACKING & ERROR BUDGETS VERIFIED GREEN!     "
echo "================================================================="
