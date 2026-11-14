#!/usr/bin/env bash
# scripts/init.sh — Argus platform baseline initialization & readiness verification
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
FAILED=0

echo "================================================================="
echo "        ARGUS PLATFORM BASELINE READINESS (init.sh)              "
echo "================================================================="

# 1. Check Git working tree
echo "[1/7] Inspecting git repository state..."
if [ -d .git ]; then
  CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
  DIRTY_COUNT=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  echo "      Git branch: ${CURRENT_BRANCH}"
  if [ "$DIRTY_COUNT" -gt 0 ]; then
    echo "      WARN: Working tree has ${DIRTY_COUNT} uncommitted changes (see clean-state-checklist)."
  else
    echo "      Git tree: clean"
  fi
else
  echo "      WARN: Not inside a git repository."
fi

# 2. Check cluster access & control-plane etcd health floor
echo "[2/7] Validating Kubernetes cluster connectivity & control-plane health floor..."
if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "      ERROR: Cannot connect to Kubernetes cluster." >&2
  FAILED=1
else
  SERVER_VERSION=$(kubectl version -o json 2>/dev/null | jq -r '.serverVersion.gitVersion' 2>/dev/null || kubectl version --short 2>/dev/null || echo "connected")
  echo "      Cluster control plane reachable (server version: ${SERVER_VERSION})"
  if [ -x "scripts/check-control-plane-health.sh" ]; then
    if ! ./scripts/check-control-plane-health.sh; then
      echo "      ERROR: Control-plane etcd apply latency / health gate failed." >&2
      FAILED=1
    fi
  fi
fi

# 4. Check required CRDs
echo "[3/7] Validating required Custom Resource Definitions (CRDs)..."
REQUIRED_CRDS=(
  "opentelemetrycollectors.opentelemetry.io"
  "instrumentations.opentelemetry.io"
  "clickhouseinstallations.clickhouse.altinity.com"
  "prometheuses.monitoring.coreos.com"
  "prometheusrules.monitoring.coreos.com"
  "servicemonitors.monitoring.coreos.com"
  "podmonitors.monitoring.coreos.com"
)

MISSING_CRDS=()
for crd in "${REQUIRED_CRDS[@]}"; do
  if ! kubectl get crd "$crd" >/dev/null 2>&1; then
    MISSING_CRDS+=("$crd")
  fi
done

if [ ${#MISSING_CRDS[@]} -gt 0 ]; then
  echo "      ERROR: Missing required CRDs:" >&2
  for crd in "${MISSING_CRDS[@]}"; do
    echo "        - $crd" >&2
  done
  FAILED=1
else
  echo "      All ${#REQUIRED_CRDS[@]} required operator CRDs are installed."
fi

# 5. Check operator Deployments in namespace
echo "[4/7] Validating operator rollout status in namespace '${NAMESPACE}'..."
if ! kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  echo "      ERROR: Namespace '${NAMESPACE}' does not exist." >&2
  FAILED=1
else
  REQUIRED_DEPLOYMENTS=(
    "opentelemetry-operator"
    "altinity-clickhouse-operator"
    "prometheus-operator-kube-p-operator"
  )

  for dep in "${REQUIRED_DEPLOYMENTS[@]}"; do
    # Check if deployment exists matching name or prefix
    DEP_NAME=$(kubectl get deploy -n "${NAMESPACE}" -o jsonpath="{.items[?(@.metadata.name=~/'${dep}'.*)].metadata.name}" 2>/dev/null || echo "")
    if [ -z "$DEP_NAME" ]; then
      # Fallback exact name search
      if kubectl get deploy "${dep}" -n "${NAMESPACE}" >/dev/null 2>&1; then
        DEP_NAME="${dep}"
      fi
    fi

    if [ -n "$DEP_NAME" ]; then
      AVAILABLE=$(kubectl get deploy "${DEP_NAME}" -n "${NAMESPACE}" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
      REPLICAS=$(kubectl get deploy "${DEP_NAME}" -n "${NAMESPACE}" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
      if [ "${AVAILABLE:-0}" -ge "${REPLICAS:-1}" ] && [ "${AVAILABLE:-0}" -gt 0 ]; then
        echo "      Deployment '${DEP_NAME}': Ready (${AVAILABLE}/${REPLICAS})"
      else
        echo "      ERROR: Deployment '${DEP_NAME}' not ready (${AVAILABLE:-0}/${REPLICAS:-1})" >&2
        FAILED=1
      fi
    else
      echo "      ERROR: Expected operator deployment matching '${dep}' not found in '${NAMESPACE}'." >&2
      FAILED=1
    fi
  done
fi

# 6. Check ClickHouse & Keeper component readiness (if deployed)
echo "[5/7] Validating ClickHouse HA and Keeper readiness (if deployed)..."
if kubectl get chi argus-clickhouse -n "${NAMESPACE}" >/dev/null 2>&1; then
  CHI_STATUS=$(kubectl get chi argus-clickhouse -n "${NAMESPACE}" -o jsonpath='{.status.status}' 2>/dev/null || echo "Unknown")
  if [ "${CHI_STATUS}" == "Completed" ]; then
    echo "      ClickHouseInstallation 'argus-clickhouse': Status Completed"
  else
    echo "      ERROR: ClickHouseInstallation 'argus-clickhouse' status is '${CHI_STATUS}' (expected Completed)" >&2
    FAILED=1
  fi
  CH_PODS=$(kubectl get pods -l clickhouse.altinity.com/chi=argus-clickhouse -n "${NAMESPACE}" -o jsonpath='{.items[*].metadata.name}')
  if [ -z "${CH_PODS}" ]; then
    echo "      ERROR: No ClickHouse pods found" >&2
    FAILED=1
  else
    for ch_pod in ${CH_PODS}; do
      if kubectl wait --for=condition=Ready "pod/${ch_pod}" -n "${NAMESPACE}" --timeout=15s >/dev/null 2>&1; then
        echo "      Pod '${ch_pod}': Ready"
      else
        echo "      ERROR: Pod '${ch_pod}' is not Ready" >&2
        FAILED=1
      fi
    done
  fi
else
  echo "      ClickHouseInstallation not deployed yet (skipping)."
fi

if kubectl get chk argus-keeper -n "${NAMESPACE}" >/dev/null 2>&1; then
  KEEPER_READY=$(kubectl get pod -l clickhouse-keeper.altinity.com/chk=argus-keeper -n "${NAMESPACE}" -o jsonpath='{.items[0].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
  if [ "${KEEPER_READY}" == "True" ]; then
    echo "      ClickHouse Keeper: Ready"
  else
    echo "      ERROR: ClickHouse Keeper pod is not Ready" >&2
    FAILED=1
  fi
fi

# 7. Check OpenTelemetry Collector pipeline readiness (if deployed)
echo "[6/7] Validating OpenTelemetry Collector pipeline readiness (if deployed)..."
if kubectl get opentelemetrycollector argus-gateway -n "${NAMESPACE}" >/dev/null 2>&1; then
  GW_AVAILABLE=$(kubectl get deploy argus-gateway-collector -n "${NAMESPACE}" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  if [ "${GW_AVAILABLE:-0}" -ge 1 ]; then
    echo "      OpenTelemetry Gateway Collector: Ready (${GW_AVAILABLE}/1)"
  else
    echo "      ERROR: OpenTelemetry Gateway Collector not ready (${GW_AVAILABLE:-0}/1)" >&2
    FAILED=1
  fi
else
  echo "      OpenTelemetry Gateway not deployed yet (skipping)."
fi

if kubectl get opentelemetrycollector argus-node-collector -n "${NAMESPACE}" >/dev/null 2>&1; then
  DS_AVAILABLE=$(kubectl get ds argus-node-collector-collector -n "${NAMESPACE}" -o jsonpath='{.status.numberAvailable}' 2>/dev/null || echo "0")
  DS_DESIRED=$(kubectl get ds argus-node-collector-collector -n "${NAMESPACE}" -o jsonpath='{.status.desiredNumberScheduled}' 2>/dev/null || echo "1")
  if [ "${DS_AVAILABLE:-0}" -ge "${DS_DESIRED:-1}" ] && [ "${DS_AVAILABLE:-0}" -gt 0 ]; then
    echo "      OpenTelemetry Node DaemonSet: Ready (${DS_AVAILABLE}/${DS_DESIRED})"
  else
    echo "      ERROR: OpenTelemetry Node DaemonSet not ready (${DS_AVAILABLE:-0}/${DS_DESIRED:-1})" >&2
    FAILED=1
  fi
else
  echo "      OpenTelemetry Node DaemonSet not deployed yet (skipping)."
fi

if kubectl get deploy argus-sample-service -n "${NAMESPACE}" >/dev/null 2>&1; then
  SAMPLE_AVAILABLE=$(kubectl get deploy argus-sample-service -n "${NAMESPACE}" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  if [ "${SAMPLE_AVAILABLE:-0}" -lt 1 ]; then
    kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=argus-sample-service -n "${NAMESPACE}" --timeout=15s >/dev/null 2>&1 || true
    SAMPLE_AVAILABLE=$(kubectl get deploy argus-sample-service -n "${NAMESPACE}" -o jsonpath='{.status.availableReplicas}' 2>/dev/null || echo "0")
  fi
  if [ "${SAMPLE_AVAILABLE:-0}" -ge 1 ]; then
    echo "      Sample Instrumented Service: Ready (${SAMPLE_AVAILABLE}/1)"
  else
    echo "      ERROR: Sample Instrumented Service not ready (${SAMPLE_AVAILABLE:-0}/1)" >&2
    FAILED=1
  fi
fi

# 9. Check architecture boundaries & Roadmap hygiene
echo "[7/7] Checking architecture boundaries and roadmap consistency..."
if [ -f "scripts/check-architecture.sh" ]; then
  ./scripts/check-architecture.sh
fi

if [ -f ".harness/ROADMAP.md" ]; then
  IN_PROGRESS_COUNT=$((grep -E 'Status.*IN PROGRESS' .harness/ROADMAP.md || true) | wc -l | tr -d ' ')
  if [ "$IN_PROGRESS_COUNT" -ne 1 ]; then
    echo "      WARN: ROADMAP.md has ${IN_PROGRESS_COUNT} features 'IN PROGRESS' (expected exactly 1)."
  else
    ACTIVE_FEATURE=$(grep -B 4 -E 'Status.*IN PROGRESS' .harness/ROADMAP.md | grep -E '^\- \[' | head -n 1 || true)
    echo "      Active feature: ${ACTIVE_FEATURE}"
  fi
fi

echo "================================================================="
if [ "$FAILED" -eq 0 ]; then
  echo "STATUS: PASS — Argus baseline is healthy and ready."
  exit 0
else
  echo "STATUS: FAIL — Argus baseline has issues listed above." >&2
  exit 1
fi
