#!/usr/bin/env bash
# deploy.sh — Full Argus platform deploy
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
SKIP_MIRROR=false
SKIP_TENANCY=false
SKIP_SLO=false

usage() {
  echo "Usage: $0 [--skip-mirror] [--skip-tenancy] [--skip-slo] [--namespace <ns>]"
  echo
  echo "  --skip-mirror    Skip image mirror setup (use when mirror is already populated)"
  echo "  --skip-tenancy   Skip ClickHouse RLS / tenant policy apply"
  echo "  --skip-slo       Skip SLO alert rules sync"
  echo "  --namespace      Target namespace (default: argus-system)"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-mirror)   SKIP_MIRROR=true ;;
    --skip-tenancy)  SKIP_TENANCY=true ;;
    --skip-slo)      SKIP_SLO=true ;;
    --namespace)     NAMESPACE="$2"; shift ;;
    -h|--help)       usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
  shift
done

step() { echo; echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

command -v kubectl   >/dev/null 2>&1 || fail "kubectl not found"
command -v helmfile  >/dev/null 2>&1 || fail "helmfile not found"

# Step 1 — Mirror
if [ "$SKIP_MIRROR" = true ]; then
  step "[1/4] Skipping mirror setup (--skip-mirror)"
else
  step "[1/4] Setting up image mirror..."
  bash deploy/mirror/setup-mirror.sh
fi

# Step 2 — Helmfile (operators + all argus workloads)
step "[2/4] Deploying via helmfile (operators → argus chart)..."
ARGUS_NAMESPACE="$NAMESPACE" helmfile apply

# Step 3 — etcd maintenance CronJob (not in helm chart)
step "[3/4] Applying control-plane etcd maintenance job..."
kubectl apply -f deploy/control-plane/etcd-maintenance.yaml -n "$NAMESPACE"

# Step 4 — Post-deploy config (needs running ClickHouse + SigNoz)
if [ "$SKIP_TENANCY" = true ]; then
  step "[4a/4] Skipping tenancy apply (--skip-tenancy)"
else
  step "[4a/4] Applying ClickHouse tenancy policies..."
  ARGUS_NAMESPACE="$NAMESPACE" bash deploy/tenancy/apply-tenancy.sh
fi

if [ "$SKIP_SLO" = true ]; then
  step "[4b/4] Skipping SLO sync (--skip-slo)"
else
  step "[4b/4] Syncing SLO alert rules..."
  ARGUS_NAMESPACE="$NAMESPACE" bash deploy/slo/apply-slo.sh
fi

echo
echo "================================================================="
echo "  Argus deploy complete. Access at: http://argus.local"
echo "  (Add cluster node IP to /etc/hosts: <node-ip>  argus.local)"
echo "================================================================="
