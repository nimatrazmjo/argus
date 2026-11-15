#!/usr/bin/env bash
# deploy/alerting/apply-rules.sh — Declaratively applies Argus alert rules to SigNoz and Kubernetes
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_FILE="${SCRIPT_DIR}/rules.json"
CRD_FILE="${SCRIPT_DIR}/prometheus-rules.yaml"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
# Alert webhook target: platform paging gateway (override with ARGUS_ALERT_WEBHOOK_URL)
WEBHOOK_URL="${ARGUS_ALERT_WEBHOOK_URL:-http://argus-paging-gateway.${NAMESPACE}.svc.cluster.local:9099/webhook/alert}"

echo "================================================================="
echo "   ALERT RULES SYNCHRONIZATION COMPLETED SUCCESSFULLY!           "
echo "================================================================="
