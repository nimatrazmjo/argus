#!/usr/bin/env bash
# deploy.sh — Full Argus platform deploy
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
SKIP_TENANCY=false
DEBUG=false
KUBE_CONTEXT="${ARGUS_KUBE_CONTEXT:-}"

usage() {
  echo "Usage: $0 [--skip-tenancy] [--namespace <ns>] [--debug] [--context <name>]"
  echo
  echo "  --skip-tenancy   Skip ClickHouse RLS / tenant policy apply"
  echo "  --namespace      Target namespace (default: argus-system)"
  echo "  --context        kube context (default: current context; env ARGUS_KUBE_CONTEXT)"
  echo "  --debug          Trace shell (set -x) + helmfile --debug"
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-tenancy)  SKIP_TENANCY=true ;;
    --debug)         DEBUG=true ;;
    --context)       KUBE_CONTEXT="$2"; shift ;;
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

# Pin ONE context for kubectl, helm, helmfile and every child script via a
# private kubeconfig, so a context switch in another terminal can't redirect
# a deploy mid-run and the global current-context is never modified.
KUBE_CONTEXT="${KUBE_CONTEXT:-$(kubectl config current-context 2>/dev/null || true)}"
[ -n "$KUBE_CONTEXT" ] || fail "no kube context (set --context or: kubectl config use-context <name>)"
PINNED_KUBECONFIG="$(mktemp -t argus-kubeconfig.XXXXXX)"
trap 'rm -f "$PINNED_KUBECONFIG"' EXIT
kubectl config view --minify --flatten --context="$KUBE_CONTEXT" > "$PINNED_KUBECONFIG" \
  || fail "context '$KUBE_CONTEXT' not found"
chmod 600 "$PINNED_KUBECONFIG"
export KUBECONFIG="$PINNED_KUBECONFIG"
echo "Using kube context: $KUBE_CONTEXT"
command -v helmfile  >/dev/null 2>&1 || fail "helmfile not found"

# Step 1 — Helmfile (operators + all argus workloads)
step "[1/3] Deploying via helmfile (operators → argus chart)..."
# sync, not apply: apply diffs all releases first, which fails on a fresh
# cluster because operator CRDs (ClickHouseInstallation, OpenTelemetryCollector,
# ServiceMonitor, PrometheusRule) don't exist until phase 1 is installed.
ARGUS_NAMESPACE="$NAMESPACE" helmfile ${HELMFILE_ARGS[@]+"${HELMFILE_ARGS[@]}"} sync

# Step 2 — etcd maintenance CronJob (not in helm chart)
step "[2/3] Applying control-plane etcd maintenance job..."
# k3s/k3d use sqlite/kine (no etcd PKI at /run/config/pki/etcd) -> job would crashloop
if kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.kubeletVersion}' 2>/dev/null | grep -q k3s; then
  echo "    skipped (k3s detected: no etcd to maintain)"
else
  kubectl apply -f deploy/control-plane/etcd-maintenance.yaml -n "$NAMESPACE"
fi

# Step 3 — Post-deploy config (needs running ClickHouse + SigNoz)
if [ "$SKIP_TENANCY" = true ]; then
  step "[3a/3] Skipping tenancy apply (--skip-tenancy)"
else
  step "[3a/3] Applying ClickHouse tenancy policies..."
  ARGUS_NAMESPACE="$NAMESPACE" bash deploy/tenancy/apply-tenancy.sh
fi

step "[3b/3] Registering SigNoz admin (needs SIGNOZ_ADMIN_PASSWORD)..."
ARGUS_NAMESPACE="$NAMESPACE" bash deploy/signoz/register-admin.sh

# Creates the argus-default-webhook channel used by alert rules
step "[3c/3] Syncing alert rules + notification channel..."
ARGUS_NAMESPACE="$NAMESPACE" bash deploy/alerting/apply-rules.sh

echo
echo "================================================================="
echo "  Argus deploy complete. Access at: http://argus.local"
if [ -f "$CRED_FILE" ]; then
  echo "  SigNoz admin: ${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
  echo "  Password file: $CRED_FILE"
fi
echo "  (Add cluster node IP to /etc/hosts: <node-ip>  argus.local)"
echo "================================================================="
