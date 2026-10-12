# Sprint Contract — F003: OTel Collector pipeline (ingest spine)

Feature: F003 — OTel Collector pipeline (ingest spine)
Phase: Phase 01 — Foundation
Date: 2026-10-12

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] Node-level DaemonSet collector deployed via `OpenTelemetryCollector` CR (kubelet/cAdvisor scrape, pod-log filelog receiver, OTLP receiver forwarding to gateway).
  - *Evidence*: `kubectl get opentelemetrycollector argus-node-collector -n argus-system` ready; DaemonSet pods running on cluster nodes.
- [x] Gateway Deployment collector deployed via `OpenTelemetryCollector` CR (batch processor, `k8sattributes` processor, ClickHouse exporter).
  - *Evidence*: `kubectl get opentelemetrycollector argus-gateway -n argus-system` ready; exposing OTLP gRPC (4317) and HTTP (4318).
- [x] OTLP metrics, logs, and traces written directly to ClickHouse via the gateway exporter.
  - *Evidence*: Test OTLP payloads sent to gateway endpoints land as rows in ClickHouse tables (`otel_traces`, `otel_metrics_gauge`, `otel_logs` / `default.otel_*`).
- [x] Records carry Kubernetes resource attributes (`k8s.namespace.name`, `k8s.pod.name`, `k8s.node.name`) populated by `k8sattributes` processor.
  - *Evidence*: SQL query on ingested rows demonstrates populated `k8s.*` resource attributes.
- [x] Single source of truth: gateway configuration manages batching, retry, and schema formatting without per-application configuration drift.
- [x] Edge cases covered:
  - Collector pod restart recovers cleanly without crash loop.
  - Malformed OTLP payload rejected with HTTP 400 without crashing gateway or node collectors.
  - ClickHouse temporarily slow or busy triggers buffer retry rather than data loss.
  - *Evidence*: `./scripts/test-otel-edge-cases.sh` passes all error condition checks.
- [x] Air-gap compliance: 100% of collector images resolved from internal mirror (`localhost:5001/argus/*`).
  - *Evidence*: Image audit in `init.sh` confirms zero public pulls.
- [x] E2E: `N/A — not user-facing` (spine pipeline verified by automated OTLP emission and ClickHouse table queries; correlation proven in F004).
- [x] No regressions: `./scripts/verify.sh` green.

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
- **Downstream error / storage slow**: ClickHouse unavailable or high latency -> gateway retry_on_failure buffer queues telemetry without dropping immediately.
- **Client error / malformed payload**: Malformed HTTP/gRPC OTLP message -> gateway returns standard gRPC InvalidArgument / HTTP 400, worker threads do not panic or restart.
- **Node agent / daemonset restart**: Node collector restarted via pod kill -> mounts resume host logs and container metrics cleanly without duplicate file lock errors.
- **RBAC permissions**: `k8sattributes` processor requires ClusterRole to query Pod/Node metadata -> declarative RBAC attached to OpenTelemetryCollector service account.

## 3. E2E scenario(s)
`N/A — not user-facing` (infrastructure telemetry pipeline; verified via automated OTLP emission script checking ClickHouse database rows).

## 4. Plan (thinnest vertical slice)
1. Ensure mirrored image `localhost:5001/argus/opentelemetry-collector-contrib:0.160.0` is registered in `deploy/mirror/images.txt`.
2. Define ClusterRole and ClusterRoleBinding for OpenTelemetry Collector to enable `k8sattributes` processor to watch Pods and Namespaces.
3. Create declarative gateway Deployment manifest [`deploy/otel/gateway.yaml`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/otel/gateway.yaml):
   - Receivers: OTLP (gRPC: 4317, HTTP: 4318).
   - Processors: `memory_limiter`, `k8sattributes`, `batch`.
   - Exporters: `clickhouse` (pointing to `chi-argus-clickhouse-argus-cluster-0-0.argus-system:9000` / `clickhouse-argus-clickhouse:9000`, database `default`, username `default`, password `argus123`).
4. Create declarative node DaemonSet manifest [`deploy/otel/node-daemonset.yaml`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/otel/node-daemonset.yaml):
   - Receivers: `kubeletstats`, `filelog` (container logs), `otlp`.
   - Exporter: `otlp` forwarding to gateway service.
5. Create deployment script [`scripts/deploy-otel.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/deploy-otel.sh).
6. Create automated pipeline test script [`scripts/test-otel-pipeline.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-otel-pipeline.sh):
   - Generates and sends sample OTLP trace, metric, and log via HTTP/gRPC.
   - Queries ClickHouse tables to assert data landed with k8s attributes.
7. Create automated edge cases test script [`scripts/test-otel-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-otel-edge-cases.sh).
8. Integrate into `scripts/verify.sh` and update tracking files.

## 5. Out of scope (parked, not built)
- SigNoz frontend UI queries (F006).
- PII / CJIS redaction processor (F005).
- Application-specific auto-instrumentation (F007).

## 6. New dependencies (with justification)
- `otel/opentelemetry-collector-contrib:0.160.0`: Contains official ClickHouse exporter and k8sattributes processor.

## 7. Risks
- ClickHouse exporter schema creation: OpenTelemetry Collector contrib's ClickHouse exporter automatically provisions tables (`otel_traces`, `otel_metrics`, `otel_logs`) on first connection if database exists.
- RBAC permissions for k8sattributes: Requires Pod and Node read permissions across cluster.
