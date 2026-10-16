#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform (35-step battery)
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/35: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/35: Running platform edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/35: Running ClickHouse HA, tiering, and persistence verification..."
./scripts/test-clickhouse-tiering.sh

echo "--> Step 4/35: Running ClickHouse HA edge cases and replication battery..."
./scripts/test-clickhouse-edge-cases.sh

echo "--> Step 5/35: Running OpenTelemetry Collector pipeline functional verification..."
./scripts/test-otel-pipeline.sh

echo "--> Step 6/35: Running OpenTelemetry Collector edge cases and resilience battery..."
./scripts/test-otel-edge-cases.sh

echo "--> Step 7/35: Running telemetry correlation (trace + metric + log 3-way join) verification..."
./scripts/test-correlation.sh

echo "--> Step 8/35: Running telemetry correlation edge cases and failure paths battery..."
./scripts/test-correlation-edge-cases.sh

echo "--> Step 9/35: Running PII and CJIS redaction at ingest verification..."
./scripts/test-redaction.sh

echo "--> Step 10/35: Running PII and CJIS redaction edge cases and resilience battery..."
./scripts/test-redaction-edge-cases.sh

echo "--> Step 11/35: Running SigNoz APM, traces, logs, and air-gap verification..."
./scripts/test-signoz.sh

echo "--> Step 12/35: Running SigNoz edge cases and resilience battery..."
./scripts/test-signoz-edge-cases.sh

echo "--> Step 13/35: Running zero-code auto-instrumentation verification..."
./scripts/test-auto-instrumentation.sh

echo "--> Step 14/35: Running zero-code auto-instrumentation edge cases and resilience battery..."
./scripts/test-auto-instrumentation-edge-cases.sh

echo "--> Step 15/35: Running eBPF Beyla network observability verification..."
./scripts/test-ebpf.sh

echo "--> Step 16/35: Running eBPF Beyla edge cases and resilience battery..."
./scripts/test-ebpf-edge-cases.sh

echo "--> Step 17/35: Running infrastructure metrics (node-exporter & kube-state-metrics) verification..."
./scripts/test-infra-metrics.sh

echo "--> Step 18/35: Running infrastructure metrics edge cases and scraping resilience battery..."
./scripts/test-infra-metrics-edge-cases.sh

echo "--> Step 19/35: Running baseline readiness and air-gap operator audit..."
./scripts/init.sh

echo "--> Step 20/35: Running continuous profiling (Pyroscope) verification..."
./scripts/test-profiling.sh

echo "--> Step 21/35: Running continuous profiling edge cases and overhead benchmark battery..."
./scripts/test-profiling-edge-cases.sh

echo "--> Step 22/35: Running ClickHouse retention, tiering, and downsampling verification..."
./scripts/test-retention-downsampling.sh

echo "--> Step 23/35: Running ClickHouse retention and downsampling edge cases battery..."
./scripts/test-retention-edge-cases.sh

echo "--> Step 24/35: Running alerting and monitors core (SigNoz Ruler & Alertmanager) verification..."
./scripts/test-alerting.sh

echo "--> Step 25/35: Running alerting edge cases, hysteresis, and deadman battery..."
./scripts/test-alerting-edge-cases.sh

echo "--> Step 26/35: Running SLO tracking and error budgets verification..."
./scripts/test-slo.sh

echo "--> Step 27/35: Running SLO edge cases, zero-division, and budget exhaustion battery..."
./scripts/test-slo-edge-cases.sh

echo "--> Step 28/35: Running incident paging path and ServiceNow routing verification..."
./scripts/test-paging.sh

echo "--> Step 29/35: Running paging retry queue and suppression edge cases battery..."
./scripts/test-paging-edge-cases.sh

echo "--> Step 30/35: Running multi-tenancy and RLS isolation verification..."
./scripts/test-tenancy.sh

echo "--> Step 31/35: Running tenancy quotas and cardinality guardrails edge cases..."
./scripts/test-tenancy-edge-cases.sh

echo "--> Step 32/35: Running synthetic canary probing and multi-step transactions..."
./scripts/test-synthetics.sh

echo "--> Step 33/35: Running synthetic probing edge cases and hysteresis battery..."
./scripts/test-synthetics-edge-cases.sh

echo "--> Step 34/35: Running Real User Monitoring (RUM) and session replay verification..."
./scripts/test-rum.sh

echo "--> Step 35/35: Running RUM PII masking correctness, large sessions, and resilience edge cases battery..."
./scripts/test-rum-edge-cases.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
