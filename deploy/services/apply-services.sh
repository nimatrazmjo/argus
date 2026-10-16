#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="argus-system"

echo "--> [1/3] Syncing microservices code into ConfigMap argus-services-code..."
kubectl create configmap argus-services-code \
  --from-file=service_template.py="${SCRIPT_DIR}/service_template.py" \
  --namespace="${NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "--> [2/3] Applying 10 Datadog-emulating microservices manifests..."
kubectl apply -f "${SCRIPT_DIR}/datadog-services.yaml"

echo "--> [3/3] Waiting for all 10 microservices to roll out successfully..."
SERVICES=(
  "argus-svc-gateway"
  "argus-svc-auth"
  "argus-svc-catalog"
  "argus-svc-order"
  "argus-svc-inventory"
  "argus-svc-payment"
  "argus-svc-billing"
  "argus-svc-shipping"
  "argus-svc-notification"
  "argus-svc-recommendation"
)

for svc in "${SERVICES[@]}"; do
  echo "    Waiting for rollout of deployment/${svc}..."
  kubectl rollout status "deployment/${svc}" -n "${NAMESPACE}" --timeout=120s
done

echo "[+] All 10 Datadog-emulating microservices successfully deployed and running!"
