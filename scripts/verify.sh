#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/27: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/27: Running platform edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/27: Running ClickHouse HA, tiering, and persistence verification..."
./scripts/test-clickhouse-tiering.sh

echo "--> Step 4/27: Running ClickHouse HA edge cases and replication battery..."
./scripts/test-clickhouse-edge-cases.sh

echo "--> Step 5/27: Running OpenTelemetry Collector pipeline functional verification..."
./scripts/test-otel-pipeline.sh

echo "--> Step 6/27: Running OpenTelemetry Collector edge cases and resilience battery..."
./scripts/test-otel-edge-cases.sh

echo "--> Step 7/27: Running telemetry correlation (trace + metric + log 3-way join) verification..."
./scripts/test-correlation.sh

echo "--> Step 8/27: Running telemetry correlation edge cases and failure paths battery..."
./scripts/test-correlation-edge-cases.sh

echo "--> Step 9/27: Running PII and CJIS redaction at ingest verification..."
./scripts/test-redaction.sh

echo "--> Step 10/27: Running PII and CJIS redaction edge cases and resilience battery..."
./scripts/test-redaction-edge-cases.sh

echo "--> Step 11/27: Running SigNoz APM, traces, logs, and air-gap verification..."
./scripts/test-signoz.sh

echo "--> Step 12/27: Running SigNoz edge cases and failure paths battery..."
./scripts/test-signoz-edge-cases.sh

echo "--> Step 13/27: Running zero-code auto-instrumentation E2E verification..."
./scripts/test-auto-instrumentation.sh

echo "--> Step 14/27: Running zero-code auto-instrumentation edge cases battery..."
./scripts/test-auto-instrumentation-edge-cases.sh

echo "--> Step 15/27: Running eBPF safety net functional and E2E verification..."
./scripts/test-ebpf.sh

echo "--> Step 16/27: Running eBPF safety net edge cases and failure paths battery..."
./scripts/test-ebpf-edge-cases.sh

echo "--> Step 17/27: Running infrastructure metrics functional and E2E verification..."
./scripts/test-infra-metrics.sh

echo "--> Step 18/27: Running infrastructure metrics edge cases and resilience battery..."
./scripts/test-infra-metrics-edge-cases.sh

echo "--> Step 19/27: Running baseline readiness and air-gap operator audit..."
./scripts/init.sh

echo "--> Step 20/27: Running continuous profiling (Pyroscope) functional verification..."
./scripts/test-profiling.sh

echo "--> Step 21/27: Running continuous profiling edge cases and overhead battery..."
./scripts/test-profiling-edge-cases.sh

echo "--> Step 22/27: Running tiered retention policies and downsampling verification..."
./scripts/test-retention-downsampling.sh

echo "--> Step 23/27: Running tiered retention and log-level filter edge cases battery..."
./scripts/test-retention-edge-cases.sh

echo "--> Step 24/27: Running alerting and monitors E2E lifecycle verification..."
./scripts/test-alerting.sh

echo "--> Step 25/27: Running alerting edge cases, hysteresis, and deadman battery..."
./scripts/test-alerting-edge-cases.sh

echo "--> Step 26/27: Running SLO tracking and error budgets verification..."
./scripts/test-slo.sh

echo "--> Step 27/27: Running SLO edge cases, zero-division, and budget exhaustion battery..."
./scripts/test-slo-edge-cases.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
