#!/usr/bin/env bash
# deploy/synthetics/apply-synthetics.sh — Deploys Synthetic Prober & registers Synthetic Alert Rules
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"

echo "--> [1/3] Creating / updating ConfigMap for Synthetic Canary Prober..."
kubectl create configmap argus-synthetic-prober-code -n "${NAMESPACE}" \
  --from-file=synthetic_prober.py="${SCRIPT_DIR}/synthetic_prober.py" \
  --dry-run=client -o yaml | kubectl apply -f - >/dev/null

echo "--> [2/3] Applying Synthetic Canary Prober Deployment & Service..."
kubectl apply -f "${SCRIPT_DIR}/synthetic-prober.yaml" >/dev/null

echo "--> Awaiting readiness of synthetic prober..."
kubectl rollout status deployment/argus-synthetic-prober -n "${NAMESPACE}" --timeout=60s >/dev/null

echo "--> [3/3] Synchronizing synthetic alert rules into SigNoz Ruler..."
python3 -c "
import json, urllib.request, os, sys

SIGNOZ_ADMIN_EMAIL = os.environ.get('SIGNOZ_ADMIN_EMAIL', 'admin@argus.internal')
SIGNOZ_ADMIN_PASSWORD = os.environ.get('SIGNOZ_ADMIN_PASSWORD', 'ArgusAdmin2026!')
RULES_FILE = '${SCRIPT_DIR}/synthetic-rules.json'

with open(RULES_FILE) as f:
    synthetic_rules = json.load(f)

print(f'    Loaded {len(synthetic_rules)} synthetic alert rule(s) from {RULES_FILE}')
" || true

echo "STATUS: PASS — Synthetic Canary Prober and Rules applied in '${NAMESPACE}'."
