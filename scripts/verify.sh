#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/3: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/3: Running edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/3: Running baseline readiness and operator audit..."
./scripts/init.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
