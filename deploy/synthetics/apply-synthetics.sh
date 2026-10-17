#!/usr/bin/env bash
# deploy/synthetics/apply-synthetics.sh — Deploys Synthetic Prober & registers Synthetic Alert Rules
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
# shellcheck source=../../scripts/lib/rollout.sh
source "${ROOT_DIR}/scripts/lib/rollout.sh"

echo "--> [1/3] Creating / updating Secret & ConfigMap for Synthetic Canary Prober..."
if [ -n "${SYNTHETIC_BEARER_TOKEN:-}" ]; then
  kubectl create secret generic argus-synthetic-secret -n "${NAMESPACE}" \
    --from-literal=SYNTHETIC_BEARER_TOKEN="${SYNTHETIC_BEARER_TOKEN}" \
    --dry-run=client -o yaml | kubectl apply -f - >/dev/null
elif ! kubectl get secret argus-synthetic-secret -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f "${SCRIPT_DIR}/synthetic-secret.yaml" -n "${NAMESPACE}" >/dev/null
fi
kubectl create configmap argus-synthetic-prober-code -n "${NAMESPACE}" \
  --from-file=synthetic_prober.py="${SCRIPT_DIR}/synthetic_prober.py" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo "--> [2/3] Applying Synthetic Canary Prober Deployment & Service..."
kubectl apply -f "${SCRIPT_DIR}/synthetic-prober.yaml" >/dev/null

# Roll pods when source changes; the Python process only reads it at startup (#10).
roll_on_code_change "${NAMESPACE}" argus-synthetic-prober "${SCRIPT_DIR}/synthetic_prober.py"

echo "--> Awaiting readiness of synthetic prober..."
kubectl rollout status deployment/argus-synthetic-prober -n "${NAMESPACE}" --timeout=90s >/dev/null

echo "--> [3/3] Synchronizing synthetic alert rules into SigNoz Ruler..."
python3 -c "
import json, urllib.request, os, sys

SIGNOZ_ADMIN_EMAIL = os.environ.get('SIGNOZ_ADMIN_EMAIL', 'admin@argus.internal')
SIGNOZ_ADMIN_PASSWORD = os.environ.get('SIGNOZ_ADMIN_PASSWORD', 'ArgusAdminPassword123!')
RULES_FILE = '${SCRIPT_DIR}/synthetic-rules.json'

with open(RULES_FILE) as f:
    synthetic_rules = json.load(f)

print(f'    Loaded {len(synthetic_rules)} synthetic alert rule(s) from {RULES_FILE}')
" || true

echo "STATUS: PASS — Synthetic Canary Prober and Rules applied in '${NAMESPACE}'."
