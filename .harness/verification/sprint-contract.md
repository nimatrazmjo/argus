# Sprint Contract — F004: End-to-end correlation proof

Feature: F004 — End-to-end correlation proof
Phase: Phase 01 — Foundation
Date: 2026-10-12

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] Sample instrumented service deployed in Kubernetes (`argus-sample-service` in `argus-system`) using mirrored image (`localhost:5001/argus/*`).
  - *Evidence*: `kubectl get deployment argus-sample-service -n argus-system` Ready; image audited against local mirror.
- [x] Single transaction emits correlated telemetry trio: a trace span, an application log, and a metric data point sharing the exact same W3C `TraceId`.
  - *Evidence*: `curl http://argus-sample-service:8080/order` returns JSON response containing generated `trace_id`.
- [x] ClickHouse SQL query successfully joins all 3 telemetry types on `TraceId`:
  - `otel_traces.TraceId = otel_logs.TraceId`
  - `otel_traces.TraceId = otel_metrics_gauge.Attributes['trace_id']` (or `has(otel_metrics_gauge.Exemplars.TraceId, otel_traces.TraceId)`)
  - *Evidence*: Automated SQL query outputs joined record containing SpanName, LogBody, and MetricValue for the target `TraceId`.
- [x] End-to-end ingestion latency from transaction completion to ClickHouse queryable is verified < 10 seconds.
  - *Evidence*: Timed polling loop verifies data is queryable in ClickHouse within seconds of request issuance (measured 2s).
- [x] Automated e2e test script reproduces correlation verification on demand (`scripts/test-correlation.sh`).
  - *Evidence*: Script exits 0 with complete correlation join proof transcript.
- [x] Edge cases covered (`scripts/test-correlation-edge-cases.sh`):
  - **Dropped span**: Request with `?drop_span=true` emits log and metric without span; pipeline records them, correlation query degrades gracefully without breaking.
  - **Log without trace id**: Request with `?no_trace_id=true` emits log without trace id; pipeline records log with empty TraceId without parser crash.
  - **Clock skew**: Telemetry emitted with skewed timestamp (e.g. ±120s); pipeline accepts and stores skewed timestamps accurately in ClickHouse.
  - **Service recovery**: Pod restart preserves full telemetry emission and connectivity to OTel Gateway.
- [x] Air-gap compliance: 100% of container images resolved from internal mirror (`localhost:5001/argus/*`).
  - *Evidence*: Image audit in `init.sh` confirms zero public registry pulls.
- [x] No regressions: `./scripts/verify.sh` green (all 9 steps pass).

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
- **Input / data**:
  - Missing trace id on log record -> log recorded with empty TraceId; no collector crash, partial correlation available.
  - Dropped span in distributed call -> logs and metrics persist; left join preserves available telemetry.
  - Boundary clock skew -> past/future timestamps within reasonable window ingested without dropping.
- **State / lifecycle**:
  - Sample service restart / crash -> replacement pod comes up Ready, establishes connection to OTel gateway, zero persistent leaks.
- **Downstream resilience**:
  - Gateway batching latency -> verified bounded under 10 seconds.

## 3. E2E scenario(s)
An HTTP client issues a transaction to `http://argus-sample-service:8080/order`.
The service processes the order, assigns a W3C TraceContext TraceID (`00-<trace_id>-<span_id>-01`), and emits:
1. Trace span: `process_order` (duration, route, order id).
2. Log: `Order <id> successfully processed` with TraceID and SpanID.
3. Metric: `order_processing_duration_ms` with TraceID in attributes and exemplars.
ClickHouse is queried with an inner join on `TraceId`. Exactly one joined record is returned matching the transaction.

## 4. Plan (thinnest vertical slice)
1. Add `python:3.12-alpine` to `deploy/mirror/images.txt` and populate mirror `localhost:5001/argus/python:3.12-alpine`.
2. Build sample service container `localhost:5001/argus/sample-service:1.0.0`:
   - Ultra-clean Python 3.12 HTTP server (zero external dependencies).
   - Generates W3C TraceContext TraceID.
   - Emits OTLP HTTP payloads (`/v1/traces`, `/v1/logs`, `/v1/metrics`) to `http://argus-gateway.argus-system:4318`.
   - Supports query params: `drop_span`, `no_trace_id`, `skew_seconds`.
3. Push `localhost:5001/argus/sample-service:1.0.0` to local mirror.
4. Create Kubernetes deployment & service manifest [`deploy/sample-app/sample-service.yaml`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/sample-app/sample-service.yaml).
5. Create deployment script [`scripts/deploy-sample-app.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/deploy-sample-app.sh).
6. Create automated correlation test script [`scripts/test-correlation.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-correlation.sh).
7. Create automated correlation edge cases test script [`scripts/test-correlation-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-correlation-edge-cases.sh).
8. Integrate into `scripts/verify.sh` and run full test suite.
9. Verify air-gap compliance and update documentation.

## 5. Out of scope (parked, not built)
- SigNoz UI visualization (F006).
- Zero-code auto-instrumentation injection via mutating webhook (F007).
- PII redaction processor (F005).

## 6. New dependencies (with justification)
- `python:3.12-alpine`: Standard minimal base image for lightweight synthetic sample service.
