#!/usr/bin/env bash
# scripts/test-edge-cases.sh — Automated tests for F001 edge cases and failure paths
set -euo pipefail

PASSED_COUNT=0
FAILED_COUNT=0

assert_failure() {
  local desc="$1"
  shift
  echo -n "Test [Edge Case]: ${desc} ... "
  if "$@" >/dev/null 2>&1; then
    echo "FAIL (expected failure, but command succeeded)"
    FAILED_COUNT=$((FAILED_COUNT + 1))
  else
    echo "PASS (correctly detected error condition)"
    PASSED_COUNT=$((PASSED_COUNT + 1))
  fi
}

assert_success() {
  local desc="$1"
  shift
  echo -n "Test [Happy/Idempotent]: ${desc} ... "
  if "$@" >/dev/null 2>&1; then
    echo "PASS"
    PASSED_COUNT=$((PASSED_COUNT + 1))
  else
    echo "FAIL (expected success, but command failed)"
    FAILED_COUNT=$((FAILED_COUNT + 1))
  fi
}

echo "=== [test-edge-cases] Running Edge Case Battery for F001 ==="

# 1. Edge Case: Mirror Unreachable Detection
assert_failure "deploy-operators.sh fails fast when mirror is unreachable" \
  env ARGUS_IMAGE_REGISTRY="127.0.0.1:59999" ./scripts/deploy-operators.sh

assert_failure "init.sh detects unreachable mirror" \
  env ARGUS_IMAGE_REGISTRY="127.0.0.1:59999" ./scripts/init.sh

# 2. Edge Case: Missing CRD Check Functionality
# Test that missing CRD check function identifies missing definitions
assert_failure "init.sh detects non-existent namespace" \
  env ARGUS_NAMESPACE="non-existent-namespace-99999" ./scripts/init.sh

# 3. Check Architecture No-op Contract
assert_success "check-architecture.sh executes cleanly (permissive until rules defined)" \
  ./scripts/check-architecture.sh

# 4. Summary
echo "=========================================================="
echo "Edge case test results: ${PASSED_COUNT} passed, ${FAILED_COUNT} failed."
if [ "$FAILED_COUNT" -gt 0 ]; then
  echo "STATUS: FAIL" >&2
  exit 1
else
  echo "STATUS: PASS"
  exit 0
fi
