#!/usr/bin/env bash
# scripts/verify.sh — Full verification suite for Argus platform (39-step battery)
set -euo pipefail

echo "================================================================="
echo "             ARGUS FULL VERIFICATION SUITE                       "
echo "================================================================="

echo "--> Step 1/43: Running architecture boundary verification..."
./scripts/check-architecture.sh

echo "--> Step 2/43: Running platform edge cases and failure paths battery..."
./scripts/test-edge-cases.sh

echo "--> Step 3/43: Running ClickHouse HA, tiering, and persistence verification..."
./scripts/test-clickhouse-tiering.sh

echo "--> Step 4/43: Running ClickHouse HA edge cases and replication battery..."
./scripts/test-clickhouse-edge-cases.sh

echo "--> Step 5/43: Running OpenTelemetry Collector pipeline functional verification..."
./scripts/test-otel-pipeline.sh

echo "--> Step 6/43: Running OpenTelemetry Collector edge cases and resilience battery..."
./scripts/test-otel-edge-cases.sh

echo "--> Step 7/43: Running telemetry correlation (trace + metric + log 3-way join) verification..."
./scripts/test-correlation.sh

echo "--> Step 8/43: Running telemetry correlation edge cases and failure paths battery..."
./scripts/test-correlation-edge-cases.sh

echo "--> Step 9/43: Running PII and CJIS redaction at ingest verification..."
./scripts/test-redaction.sh

echo "--> Step 10/43: Running PII and CJIS redaction edge cases and resilience battery..."
./scripts/test-redaction-edge-cases.sh

echo "--> Step 11/43: Running SigNoz APM, traces, logs, and air-gap verification..."
./scripts/test-signoz.sh

echo "--> Step 12/43: Running SigNoz edge cases and resilience battery..."
./scripts/test-signoz-edge-cases.sh

echo "--> Step 13/43: Running zero-code auto-instrumentation verification..."
./scripts/test-auto-instrumentation.sh

echo "--> Step 14/43: Running zero-code auto-instrumentation edge cases and resilience battery..."
./scripts/test-auto-instrumentation-edge-cases.sh

echo "--> Step 15/43: Running eBPF Beyla network observability verification..."
./scripts/test-ebpf.sh

echo "--> Step 16/43: Running eBPF Beyla edge cases and resilience battery..."
./scripts/test-ebpf-edge-cases.sh

echo "--> Step 17/43: Running infrastructure metrics (node-exporter & kube-state-metrics) verification..."
./scripts/test-infra-metrics.sh

echo "--> Step 18/43: Running infrastructure metrics edge cases and scraping resilience battery..."
./scripts/test-infra-metrics-edge-cases.sh

echo "--> Step 19/43: Running baseline readiness and air-gap operator audit..."
./scripts/init.sh

echo "--> Step 20/43: Running continuous profiling (Pyroscope) verification..."
./scripts/test-profiling.sh

echo "--> Step 21/43: Running continuous profiling edge cases and overhead benchmark battery..."
./scripts/test-profiling-edge-cases.sh

echo "--> Step 22/43: Running ClickHouse retention, tiering, and downsampling verification..."
./scripts/test-retention-downsampling.sh

echo "--> Step 23/43: Running ClickHouse retention and downsampling edge cases battery..."
./scripts/test-retention-edge-cases.sh

echo "--> Step 24/43: Running alerting and monitors core (SigNoz Ruler & Alertmanager) verification..."
./scripts/test-alerting.sh

echo "--> Step 25/43: Running alerting edge cases, hysteresis, and deadman battery..."
./scripts/test-alerting-edge-cases.sh

echo "--> Step 26/43: Running SLO tracking and error budgets verification..."
./scripts/test-slo.sh

echo "--> Step 27/43: Running SLO edge cases, zero-division, and budget exhaustion battery..."
./scripts/test-slo-edge-cases.sh

echo "--> Step 28/43: Running incident paging path and ServiceNow routing verification..."
./scripts/test-paging.sh

echo "--> Step 29/43: Running paging retry queue and suppression edge cases battery..."
./scripts/test-paging-edge-cases.sh

echo "--> Step 30/43: Running multi-tenancy and RLS isolation verification..."
./scripts/test-tenancy.sh

echo "--> Step 31/43: Running tenancy quotas and cardinality guardrails edge cases..."
./scripts/test-tenancy-edge-cases.sh

echo "--> Step 32/43: Running synthetic canary probing and multi-step transactions..."
./scripts/test-synthetics.sh

echo "--> Step 33/43: Running synthetic probing edge cases and hysteresis battery..."
./scripts/test-synthetics-edge-cases.sh

echo "--> Step 34/43: Running Real User Monitoring (RUM) and session replay verification..."
./scripts/test-rum.sh

echo "--> Step 35/43: Running RUM PII masking correctness, large sessions, and resilience edge cases battery..."
./scripts/test-rum-edge-cases.sh

echo "--> Step 36/43: Running Agency SSO and RBAC role mapping verification..."
./scripts/test-sso.sh

echo "--> Step 37/43: Running SSO authentication failure, unassigned role, and token expiry battery..."
./scripts/test-sso-edge-cases.sh

echo "--> Step 38/43: Running Dynamic Anomaly and Forecast Monitors verification..."
./scripts/test-anomaly.sh

echo "--> Step 39/43: Running Anomaly Monitors cold start, sparse data, and regime shift edge cases battery..."
./scripts/test-anomaly-edge-cases.sh

echo "--> Step 40/43: Running Topological Alert Correlation and Root-Cause Grouping verification..."
./scripts/test-correlation-grouping.sh

echo "--> Step 41/43: Running Alert Correlation edge cases, anti-false-merge, and cycle guardrail battery..."
./scripts/test-correlation-grouping-edge-cases.sh

echo "--> Step 42/43: Running Natural Language Telemetry Query and Incident Summarization verification..."
./scripts/test-nl-query.sh

echo "--> Step 43/43: Running NL Query, Prompt Injection, and Boundary Guardrails edge cases battery..."
./scripts/test-nl-query-edge-cases.sh

echo "================================================================="
echo "STATUS: ALL VERIFICATIONS PASSED"
echo "================================================================="
