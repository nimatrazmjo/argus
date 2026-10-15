#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/33: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/33: Running platform edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/33: Running ClickHouse HA, tiering, and persistence verification..."
./scripts/test-clickhouse-tiering.sh

echo "--> Step 4/33: Running ClickHouse HA edge cases and replication battery..."
./scripts/test-clickhouse-edge-cases.sh

echo "--> Step 5/33: Running OpenTelemetry Collector pipeline functional verification..."
./scripts/test-otel-pipeline.sh

echo "--> Step 6/33: Running OpenTelemetry Collector edge cases and resilience battery..."
./scripts/test-otel-edge-cases.sh

echo "--> Step 7/33: Running telemetry correlation (trace + metric + log 3-way join) verification..."
./scripts/test-correlation.sh

echo "--> Step 8/33: Running telemetry correlation edge cases and failure paths battery..."
./scripts/test-correlation-edge-cases.sh

echo "--> Step 9/33: Running PII and CJIS redaction at ingest verification..."
./scripts/test-redaction.sh

echo "--> Step 10/33: Running PII and CJIS redaction edge cases and resilience battery..."
./scripts/test-redaction-edge-cases.sh

echo "--> Step 11/33: Running SigNoz APM, traces, logs, and air-gap verification..."
./scripts/test-signoz.sh

echo "--> Step 12/33: Running SigNoz edge cases and failure paths battery..."
./scripts/test-signoz-edge-cases.sh

echo "--> Step 13/33: Running zero-code auto-instrumentation E2E verification..."
./scripts/test-auto-instrumentation.sh

echo "--> Step 14/33: Running zero-code auto-instrumentation edge cases battery..."
./scripts/test-auto-instrumentation-edge-cases.sh

echo "--> Step 15/33: Running eBPF safety net functional and E2E verification..."
./scripts/test-ebpf.sh

echo "--> Step 16/33: Running eBPF safety net edge cases and failure paths battery..."
./scripts/test-ebpf-edge-cases.sh

echo "--> Step 17/33: Running infrastructure metrics functional and E2E verification..."
./scripts/test-infra-metrics.sh

echo "--> Step 18/33: Running infrastructure metrics edge cases and resilience battery..."
./scripts/test-infra-metrics-edge-cases.sh

echo "--> Step 19/33: Running baseline readiness and air-gap operator audit..."
./scripts/init.sh

echo "--> Step 20/33: Running continuous profiling (Pyroscope) functional verification..."
./scripts/test-profiling.sh

echo "--> Step 21/33: Running continuous profiling edge cases and overhead battery..."
./scripts/test-profiling-edge-cases.sh

echo "--> Step 22/33: Running tiered retention policies and downsampling verification..."
./scripts/test-retention-downsampling.sh

echo "--> Step 23/33: Running tiered retention and log-level filter edge cases battery..."
./scripts/test-retention-edge-cases.sh

echo "--> Step 24/33: Running alerting and monitors E2E lifecycle verification..."
./scripts/test-alerting.sh

echo "--> Step 25/33: Running alerting edge cases, hysteresis, and deadman battery..."
./scripts/test-alerting-edge-cases.sh

echo "--> Step 26/33: Running SLO tracking and error budgets verification..."
./scripts/test-slo.sh

echo "--> Step 27/33: Running SLO edge cases, zero-division, and budget exhaustion battery..."
./scripts/test-slo-edge-cases.sh

echo "--> Step 28/33: Running incident paging path and ServiceNow routing verification..."
./scripts/test-paging.sh

echo "--> Step 29/33: Running paging retry queue and suppression edge cases battery..."
./scripts/test-paging-edge-cases.sh

echo "--> Step 30/33: Running multi-tenancy and RLS isolation verification..."
./scripts/test-tenancy.sh

echo "--> Step 31/33: Running tenancy quotas and cardinality guardrails edge cases..."
./scripts/test-tenancy-edge-cases.sh

echo "--> Step 32/33: Running synthetic canary probing and multi-step transactions..."
./scripts/test-synthetics.sh

echo "--> Step 33/33: Running synthetic probing edge cases and hysteresis battery..."
./scripts/test-synthetics-edge-cases.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
