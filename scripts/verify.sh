#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/15: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/15: Running platform edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/15: Running ClickHouse HA, tiering, and persistence verification..."
./scripts/test-clickhouse-tiering.sh

echo "--> Step 4/15: Running ClickHouse HA edge cases and replication battery..."
./scripts/test-clickhouse-edge-cases.sh

echo "--> Step 5/15: Running OpenTelemetry Collector pipeline functional verification..."
./scripts/test-otel-pipeline.sh

echo "--> Step 6/15: Running OpenTelemetry Collector edge cases and resilience battery..."
./scripts/test-otel-edge-cases.sh

echo "--> Step 7/15: Running telemetry correlation (trace + metric + log 3-way join) verification..."
./scripts/test-correlation.sh

echo "--> Step 8/15: Running telemetry correlation edge cases and failure paths battery..."
./scripts/test-correlation-edge-cases.sh

echo "--> Step 9/15: Running PII and CJIS redaction at ingest verification..."
./scripts/test-redaction.sh

echo "--> Step 10/15: Running PII and CJIS redaction edge cases and resilience battery..."
./scripts/test-redaction-edge-cases.sh

echo "--> Step 11/15: Running SigNoz APM, traces, logs, and air-gap verification..."
./scripts/test-signoz.sh

echo "--> Step 12/15: Running SigNoz edge cases and failure paths battery..."
./scripts/test-signoz-edge-cases.sh

echo "--> Step 13/15: Running zero-code auto-instrumentation E2E verification..."
./scripts/test-auto-instrumentation.sh

echo "--> Step 14/15: Running zero-code auto-instrumentation edge cases battery..."
./scripts/test-auto-instrumentation-edge-cases.sh

echo "--> Step 15/15: Running baseline readiness and air-gap operator audit..."
./scripts/init.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
