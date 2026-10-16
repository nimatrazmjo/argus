#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
STAGGER_DELAY_SECONDS="${STAGGER_DELAY_SECONDS:-2}"
MAX_KUBECTL_RETRIES="${MAX_KUBECTL_RETRIES:-5}"

# Retry wrapper to protect against transient kube-apiserver / etcd I/O timeouts
kubectl_retry() {
  local attempt=1
  local backoff=2
  while true; do
    if kubectl "$@"; then
      return 0
    fi
    if [ "${attempt}" -ge "${MAX_KUBECTL_RETRIES}" ]; then
      echo "[-] kubectl command failed after ${attempt} attempts: kubectl $*" >&2
      return 1
    fi
    echo "    [!] Transient control-plane timeout on 'kubectl $*' (attempt ${attempt}/${MAX_KUBECTL_RETRIES}). Retrying in ${backoff}s..." >&2
    sleep "${backoff}"
    attempt=$((attempt + 1))
    backoff=$((backoff * 2))
  done
}

echo "--> [1/3] Syncing microservices code into ConfigMap argus-services-code..."
kubectl create configmap argus-services-code \
  --from-file=service_template.py="${SCRIPT_DIR}/service_template.py" \
  --namespace="${NAMESPACE}" \
  --dry-run=client -o yaml | kubectl_retry apply -f -

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

echo "--> [2/3] Applying and rolling out 10 Datadog-emulating microservices in staggered sequence (throttling etcd write bursts)..."
idx=0
total="${#SERVICES[@]}"
for svc in "${SERVICES[@]}"; do
  idx=$((idx + 1))
  echo "    [${idx}/${total}] Applying manifest for ${svc}..."
  python3 - "${SCRIPT_DIR}/datadog-services.yaml" "${svc}" <<'PYEOF' | kubectl_retry apply -n "${NAMESPACE}" -f -
import sys

manifest_path, target_svc = sys.argv[1], sys.argv[2]
with open(manifest_path, "r", encoding="utf-8") as f:
    content = f.read()

docs = [d.strip() for d in content.split("\n---") if d.strip()]
matched = [d for d in docs if f"name: {target_svc}\n" in d or d.endswith(f"name: {target_svc}")]
if not matched:
    sys.exit(f"No manifest documents found for {target_svc}")
print("\n---\n".join(matched))
PYEOF

  echo "    [${idx}/${total}] Waiting for rollout of deployment/${svc}..."
  kubectl_retry rollout status "deployment/${svc}" -n "${NAMESPACE}" --timeout=120s

  if [ "${idx}" -lt "${total}" ] && [ "${STAGGER_DELAY_SECONDS}" -gt 0 ]; then
    sleep "${STAGGER_DELAY_SECONDS}"
  fi
done

echo "--> [3/3] Verifying all 10 microservices are Ready..."
for svc in "${SERVICES[@]}"; do
  kubectl_retry rollout status "deployment/${svc}" -n "${NAMESPACE}" --timeout=60s >/dev/null
done

echo "[+] All 10 Datadog-emulating microservices successfully deployed and running!"
