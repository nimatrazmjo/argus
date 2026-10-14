#!/usr/bin/env bash
# scripts/test-profiling.sh — Functional & E2E verification for F010 (Continuous Profiling)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "${SCRIPT_DIR}")"
NAMESPACE="argus-system"
EVIDENCE_DIR="${ROOT_DIR}/.harness/evidence/F010"
mkdir -p "${EVIDENCE_DIR}"

echo "================================================================="
echo "       F010: CONTINUOUS PROFILING (PYROSCOPE) VERIFICATION       "
echo "================================================================="

# Helper to exec in sample-service pod (Docker-first execution with kubectl fallback)
exec_sample_app() {
  local py_code="$1"
  local cid
  cid=$(docker ps -q --filter "name=k8s_sample-service_argus-sample-service" | head -n 1)
  if [[ -n "${cid}" ]]; then
    local res
    if res=$(docker exec "${cid}" python -c "${py_code}" 2>/dev/null || docker exec "${cid}" python3 -c "${py_code}" 2>/dev/null); then
      echo "${res}"
      return 0
    fi
  fi
  kubectl exec --request-timeout=5s -n "${NAMESPACE}" deploy/argus-sample-service -- python3 -c "${py_code}" 2>/dev/null || echo "FAIL"
}

# Test 1: Air-gapped container image compliance
echo "--> Test 1: Verifying air-gap image provenance for Pyroscope..."
PYROSCOPE_IMAGE=$(kubectl get deploy pyroscope -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].image}')

if [[ "${PYROSCOPE_IMAGE}" =~ ^localhost:5001/argus/pyroscope: ]]; then
  echo "  [PASS] Pyroscope image: ${PYROSCOPE_IMAGE} (local mirror verified)"
else
  echo "  [FAIL] Pyroscope image does not resolve from localhost:5001/argus/: ${PYROSCOPE_IMAGE}"
  exit 1
fi

if grep -q "grafana/pyroscope:1.7.1" "${ROOT_DIR}/deploy/mirror/images.txt"; then
  echo "  [PASS] deploy/mirror/images.txt indexes upstream grafana/pyroscope:1.7.1"
else
  echo "  [FAIL] deploy/mirror/images.txt missing grafana/pyroscope:1.7.1 entry"
  exit 1
fi

# Test 2: Pod Health and Readiness
echo "--> Test 2: Verifying pod readiness for Pyroscope..."
kubectl rollout status deploy/pyroscope -n "${NAMESPACE}" --timeout=120s

PYRO_POD_STATUS=$(kubectl get pods -n "${NAMESPACE}" -l app.kubernetes.io/name=pyroscope -o jsonpath='{.items[0].status.containerStatuses[0].ready}')
if [[ "${PYRO_POD_STATUS}" == "true" ]]; then
  echo "  [PASS] Pyroscope workload is 1/1 Running and Ready"
else
  echo "  [FAIL] Pyroscope container ready status is ${PYRO_POD_STATUS}"
  exit 1
fi

# Test 3: Raw Profiling Endpoints and Egress Prohibitions
echo "--> Test 3: Validating Pyroscope health endpoint and telemetry suppression..."
READY_CHECK=$(exec_sample_app "import urllib.request; resp = urllib.request.urlopen('http://pyroscope.argus-system.svc.cluster.local:4040/ready', timeout=5); print('OK' if resp.status == 200 else 'FAIL')")
if [[ "${READY_CHECK}" == "OK" ]]; then
  echo "  [PASS] Pyroscope /ready endpoint responded 200 OK from inside the cluster"
else
  echo "  [FAIL] Pyroscope /ready check failed: ${READY_CHECK}"
  exit 1
fi

# Check that phone-home usage stats are explicitly disabled
USAGE_FLAG=$(kubectl get deploy pyroscope -n "${NAMESPACE}" -o jsonpath='{.spec.template.spec.containers[0].args}')
if [[ "${USAGE_FLAG}" == *"-usage-stats.enabled=false"* ]]; then
  echo "  [PASS] Telemetry / phone-home disabled (-usage-stats.enabled=false verified for air-gap)"
else
  echo "  [FAIL] Missing -usage-stats.enabled=false flag on Pyroscope deployment"
  exit 1
fi

# Test 4: Profile Data Ingestion via Sample Service
echo "--> Test 4: Verifying continuous profiling data ingestion from argus-sample-service..."
TRIGGER_RES=$(exec_sample_app "import urllib.request, json; resp = urllib.request.urlopen('http://127.0.0.1:8080/api/profile/trigger', timeout=5); data = json.loads(resp.read().decode()); print('OK' if data.get('cpu_emitted') and data.get('memory_emitted') else 'FAIL')")

if [[ "${TRIGGER_RES}" == "OK" ]]; then
  echo "  [PASS] argus-sample-service successfully emitted CPU and Memory profile batches"
else
  echo "  [FAIL] Failed to trigger and emit profile data: ${TRIGGER_RES}"
  exit 1
fi

# Test 5: Flame Graph Render API Functional Verification (CPU)
echo "--> Test 5: Validating Flame Graph Render API (CPU Profile)..."
CPU_RENDER_RESULT=$(exec_sample_app "
import urllib.request, json, time
now = int(time.time())
url = 'http://pyroscope.argus-system.svc.cluster.local:4040/pyroscope/render?query=process_cpu:cpu:nanoseconds:cpu:nanoseconds%7Bservice_name=%22argus-sample-service%22%7D&from=' + str(now - 300) + '&until=' + str(now + 60)
req = urllib.request.urlopen(url, timeout=5)
data = json.loads(req.read().decode())
fb = data.get('flamebearer', {})
num_ticks = fb.get('numTicks', 0)
names = fb.get('names', [])
levels = fb.get('levels', [])
if num_ticks > 0 and len(names) > 1 and len(levels) > 0:
    print('OK:' + str(num_ticks) + ':' + str(len(names)) + ':' + str(len(levels)))
else:
    print('EMPTY:' + str(num_ticks) + ':' + str(len(names)))
")

if [[ "${CPU_RENDER_RESULT}" =~ ^OK: ]]; then
  echo "  [PASS] CPU Flame graph render verified: ${CPU_RENDER_RESULT}"
else
  echo "  [FAIL] CPU Flame graph returned unexpected data: ${CPU_RENDER_RESULT}"
  exit 1
fi

# Test 6: Flame Graph Render API Functional Verification (Memory / alloc_space)
echo "--> Test 6: Validating Flame Graph Render API (Memory Profile)..."
MEM_RENDER_RESULT=$(exec_sample_app "
import urllib.request, json, time
now = int(time.time())
url = 'http://pyroscope.argus-system.svc.cluster.local:4040/pyroscope/render?query=memory:alloc_space:bytes::%7Bservice_name=%22argus-sample-service%22%7D&from=' + str(now - 300) + '&until=' + str(now + 60)
req = urllib.request.urlopen(url, timeout=5)
data = json.loads(req.read().decode())
fb = data.get('flamebearer', {})
num_ticks = fb.get('numTicks', 0)
names = fb.get('names', [])
levels = fb.get('levels', [])
units = data.get('metadata', {}).get('units', '')
if num_ticks > 0 and len(names) > 1 and len(levels) > 0 and units == 'bytes':
    print('OK:' + str(num_ticks) + ':' + str(len(names)) + ':' + units)
else:
    print('EMPTY:' + str(num_ticks) + ':' + str(len(names)) + ':' + units)
")

if [[ "${MEM_RENDER_RESULT}" =~ ^OK: ]]; then
  echo "  [PASS] Memory Flame graph render verified: ${MEM_RENDER_RESULT}"
else
  echo "  [FAIL] Memory Flame graph returned unexpected data: ${MEM_RENDER_RESULT}"
  exit 1
fi

# Test 7: Export Flame Graph JSON Evidence
echo "--> Test 7: Capturing Flame Graph render evidence into .harness/evidence/F010/..."
exec_sample_app "
import urllib.request, time
now = int(time.time())
url = 'http://pyroscope.argus-system.svc.cluster.local:4040/pyroscope/render?query=process_cpu:cpu:nanoseconds:cpu:nanoseconds%7Bservice_name=%22argus-sample-service%22%7D&from=' + str(now - 300) + '&until=' + str(now + 60)
req = urllib.request.urlopen(url, timeout=5)
print(req.read().decode())
" > "${EVIDENCE_DIR}/flamegraph-cpu.json"

exec_sample_app "
import urllib.request, time
now = int(time.time())
url = 'http://pyroscope.argus-system.svc.cluster.local:4040/pyroscope/render?query=memory:alloc_space:bytes::%7Bservice_name=%22argus-sample-service%22%7D&from=' + str(now - 300) + '&until=' + str(now + 60)
req = urllib.request.urlopen(url, timeout=5)
print(req.read().decode())
" > "${EVIDENCE_DIR}/flamegraph-memory.json"

if [[ -s "${EVIDENCE_DIR}/flamegraph-cpu.json" && -s "${EVIDENCE_DIR}/flamegraph-memory.json" ]]; then
  echo "  [PASS] Evidence files flamegraph-cpu.json and flamegraph-memory.json captured successfully"
else
  echo "  [FAIL] Evidence files failed to save or are empty"
  exit 1
fi

echo "================================================================="
echo "STATUS: ALL F010 CONTINUOUS PROFILING TESTS PASSED (100% GREEN) "
echo "================================================================="
