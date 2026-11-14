#!/usr/bin/env bash
# deploy.sh — Full Argus platform deploy
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
SKIP_TENANCY=false
SKIP_SLO=false
DEBUG=false

usage() {
  echo "Usage: $0 [--skip-tenancy] [--skip-slo] [--namespace <ns>] [--debug]"
  echo
  echo "  --skip-tenancy   Skip ClickHouse RLS / tenant policy apply"
  echo "  --skip-slo       Skip SLO alert rules sync"
  echo "  --namespace      Target namespace (default: argus-system)"
  echo "  --debug          Trace shell (set -x) + helmfile --debug"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-tenancy)  SKIP_TENANCY=true ;;
    --skip-slo)      SKIP_SLO=true ;;
    --debug)         DEBUG=true ;;
    --namespace)     NAMESPACE="$2"; shift ;;
    -h|--help)       usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
  shift
done

HELMFILE_ARGS=()
if [ "$DEBUG" = true ]; then
  set -x
  HELMFILE_ARGS+=(--debug)
fi

# SigNoz admin creds: env wins, else the host-side file (chmod 600)
CRED_FILE="${ARGUS_CRED_FILE:-$HOME/.argus/signoz-admin.env}"
if [ -z "${SIGNOZ_ADMIN_PASSWORD:-}" ] && [ -f "$CRED_FILE" ]; then
  set -a; . "$CRED_FILE"; set +a
fi

step() { echo; echo "==> $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

command -v kubectl   >/dev/null 2>&1 || fail "kubectl not found"
command -v helmfile  >/dev/null 2>&1 || fail "helmfile not found"

# Step 1 — Build in-repo sample image (local Docker; colima k3s w/ docker runtime shares the image store)
step "[1/4] Building sample service image..."
command -v docker >/dev/null 2>&1 || fail "docker not found"
docker build -t argus/sample-service:1.0.0 deploy/sample-app/app

# Step 2 — Helmfile (operators + all argus workloads)
step "[2/4] Deploying via helmfile (operators → argus chart)..."
# sync, not apply: apply diffs all releases first, which fails on a fresh
# cluster because operator CRDs (ClickHouseInstallation, OpenTelemetryCollector,
# ServiceMonitor, PrometheusRule) don't exist until phase 1 is installed.
ARGUS_NAMESPACE="$NAMESPACE" helmfile ${HELMFILE_ARGS[@]+"${HELMFILE_ARGS[@]}"} sync

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

step "[4b/4] Registering SigNoz admin (needs SIGNOZ_ADMIN_PASSWORD)..."
ARGUS_NAMESPACE="$NAMESPACE" bash deploy/signoz/register-admin.sh

# Creates the argus-default-webhook channel that the SLO rules below reference
step "[4c/4] Syncing alert rules + notification channel..."
ARGUS_NAMESPACE="$NAMESPACE" bash deploy/alerting/apply-rules.sh

if [ "$SKIP_SLO" = true ]; then
  step "[4d/4] Skipping SLO sync (--skip-slo)"
else
  step "[4d/4] Syncing SLO alert rules..."
  ARGUS_NAMESPACE="$NAMESPACE" bash deploy/slo/apply-slo.sh
fi

echo
echo "================================================================="
echo "  Argus deploy complete. Access at: http://argus.local"
if [ -f "$CRED_FILE" ]; then
  echo "  SigNoz admin: ${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
  echo "  Password file: $CRED_FILE"
fi
echo "  (Add cluster node IP to /etc/hosts: <node-ip>  argus.local)"
echo "================================================================="
