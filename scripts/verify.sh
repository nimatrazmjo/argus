#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/11: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/11: Running platform edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/11: Running ClickHouse HA, tiering, and persistence verification..."
./scripts/test-clickhouse-tiering.sh

echo "--> Step 4/11: Running ClickHouse HA edge cases and replication battery..."
./scripts/test-clickhouse-edge-cases.sh

echo "--> Step 5/11: Running OpenTelemetry Collector pipeline functional verification..."
./scripts/test-otel-pipeline.sh

echo "--> Step 6/11: Running OpenTelemetry Collector edge cases and resilience battery..."
./scripts/test-otel-edge-cases.sh

echo "--> Step 7/11: Running telemetry correlation (trace + metric + log 3-way join) verification..."
./scripts/test-correlation.sh

echo "--> Step 8/11: Running telemetry correlation edge cases and failure paths battery..."
./scripts/test-correlation-edge-cases.sh

echo "--> Step 9/11: Running PII and CJIS redaction at ingest verification..."
./scripts/test-redaction.sh

echo "--> Step 10/11: Running PII and CJIS redaction edge cases and resilience battery..."
./scripts/test-redaction-edge-cases.sh

echo "--> Step 11/11: Running baseline readiness and air-gap operator audit..."
./scripts/init.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
