# CHANGELOG — completed implementation, with evidence

Newest first. One entry per feature that reached `COMPLETE`. An entry is not valid without
reproducible evidence (see `verification/acceptance-evidence.md`).

## Template
```
## <YYYY-MM-DD> — <FID> <feature name> — COMPLETE
Branch/commit: <branch> @ <sha>   PR: <url>   CI: <green + link>
Evidence:
  - <exact command> -> <result / test id / artifact path>
  - full suite: <command> -> <N passed, 0 failed> (no regressions)
  - e2e: <command> -> <scenarios passed / N-A not user-facing> (trace: .harness/evidence/<FID>/)
  - edge cases: <the applicable edge-cases.md categories covered, by test>
Evaluator: acceptance=_ correctness=_ boundaries=_ modularity=_ evidence=_ => avg _._  (PASS)
Notes: <anything the next agent should know>
```

<!-- entries go below, newest first -->
## 2026-10-15 — F012 SLO Tracking, Error Budget Burndown & Burn Rate Monitors — COMPLETE
Branch/commit: main @ HEAD   PR: N/A   CI: green (27/27 verification steps passed)
Evidence:
  - Architecture Decision & Implementation:
      * `docs/decisions/ADR-0008-slo-tracking-and-error-budgets.md`: OpenSLO-compatible specification, multi-window multi-burn-rate alerting architecture, in-service error budget accountant.
      * `deploy/slo/slo-definition.json`: Declarative OpenSLO manifest defining 99.0% availability SLO with 500ms latency SLI.
      * `deploy/slo/slo-rules.json`: Multi-window burn-rate rules for SigNoz Ruler (Fast Burn 14.4x / Slow Burn 6x / Budget Exhausted / SLI Breach).
      * `deploy/slo/apply-slo.sh`: Declarative CLI controller synchronizing SLO rules to SigNoz API and generating OpenSLO manifests.
      * `deploy/sample-app/app/server.py`: In-memory thread-safe `SLOTracker` with rolling event window, Availability/Latency SLI computation, error budget tracking, and visual HTML status dashboard (`/slo`).
  - End-to-End Verification:
      * `scripts/test-slo.sh` + `scripts/run_slo_e2e.py`: Verified clean baseline -> synthetic good traffic -> fault injection burning error budget (SLI dropped to 95.238%, Budget Consumed 476.19%, Burn Rate 4.76x) -> visual dashboard inspection -> active SigNoz Ruler monitors (4/4 confirmed) -> clean reset.
      * Generated evidence artifacts in `.harness/evidence/F012/`: `slo-definition.json`, `slo-status-baseline.json`, `slo-status-post-burn.json`, `slo-dashboard-proof.html`, `slo-alert-rules-synced.json`.
  - Edge Cases & Resilience Battery:
      * `scripts/test-slo-edge-cases.sh` + `scripts/run_slo_edge_cases.py`:
          1. Zero-traffic window & division-by-zero safety (100% SLI, NO_TRAFFIC status).
          2. Error budget exhaustion clamping (remaining budget clamped to 0.0%, CRITICAL_EXHAUSTED).
          3. Fast burn rate detection (15.0x > 14.4x critical threshold).
          4. Slow burn rate detection (8.0x > 6.0x warning threshold).
          5. Orthogonal latency SLI breach without HTTP 5xx errors (Availability: 100%, Latency SLI: 50%).
          6. In-memory alert webhook reception & instant recovery reset.
      * Evidence saved to `.harness/evidence/F012/edge-cases-verification.txt`.
  - Platform Stability Fixes:
      * ClickHouse HA: raised container CPU limit to 6 cores, eliminating 95.5% CFS throttling.
      * Telemetry correlation: synchronous distributed inserts (`insert_distributed_sync=1`) and missing replica fallback checks reducing query latency from 207s to 2s.
      * Full verification suite: 27/27 tests passed 100% green.
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: F012 is COMPLETE. Progress is 13/21 features (62%). Ready for next Wave 3 work packages: F013 (Paging Webhook) & F015 (Multi-Tenancy).
Branch/commit: main @ HEAD   PR: N/A   CI: green
Evidence:
  - Architecture Decision & Manifests:
      * `docs/decisions/ADR-0007-alerting-and-monitors-signoz.md` documenting SigNoz Ruler + Alertmanager deduplication engine.
      * `deploy/alerting/rules.json`: Declarative JSON alert rules covering CPU threshold, memory threshold, flapping hysteresis (2m window), deadman absence monitoring, and high-cardinality containers.
      * `deploy/alerting/apply-rules.sh`: Declarative synchronization script updating SigNoz Ruler and applying Kubernetes `PrometheusRule` CRD.
      * `deploy/alerting/prometheus-rules.yaml`: Kubernetes-native `monitoring.coreos.com/v1` PrometheusRule manifests.
  - End-to-End Verification:
      * `scripts/test-alerting.sh` + `scripts/run_alert_e2e.py`: Verified metric breach -> firing transition -> Alertmanager deduplication -> recovery/resolution lifecycle.
      * Generated evidence artifacts: `.harness/evidence/F011/alert-firing-proof.json`, `.harness/evidence/F011/alert-dedup-proof.json`, `.harness/evidence/F011/alert-resolved-proof.json`.
  - Edge Cases & Resilience Battery:
      * `scripts/test-alerting-edge-cases.sh`: Verified flapping prevention (2m evaluation window), deadman absence handling (inverted comparison on zero metrics), and high-cardinality aggregation query performance (<5000ms latency requirement). Evidence saved to `.harness/evidence/F011/edge-cases-verification.txt`.
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: F011 is COMPLETE! Wave 2 is 100% complete (12/21 features — 57%). Synchronization Gate G2 is PASSED.

## 2026-10-15 — F014 Tiered Retention Policies, Downsampling Materialized Views & Log Filtering — COMPLETE
Branch/commit: main @ c02c5ae   PR: N/A   CI: green
Evidence:
  - Storage Policies & Materialized Views:
      * `deploy/clickhouse/retention-policies.sql`: Hot NVMe local SSD -> Cold S3/SeaweedFS tiered volume migration and drop TTLs.
      * Materialized views for 1-minute (`otel_metrics_1m`, `signoz_metrics.samples_1m`) and 1-hour rollups.
      * `deploy/otel/processors/filter-processor.yaml`: Collector log-level filter dropping debug noise at ingest.
  - Test Suites & Verification:
      * `scripts/test-retention-downsampling.sh`: Verified volume tiering, TTL syntax, downsampling table rollups.
      * `scripts/test-retention-edge-cases.sh`: Verified S3 failover, backpressure under high volume, and log filter accuracy. Evidence in `.harness/evidence/F014/`.
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)

## 2026-10-14 — F010 Continuous Profiling via Grafana Pyroscope — COMPLETE
Branch/commit: main @ 7b624e1   PR: N/A   CI: green
Evidence:
  - Architecture Decision & Deployment:
      * `docs/decisions/ADR-0006-continuous-profiling-pyroscope.md` selecting Grafana Pyroscope in single-binary mode.
      * `deploy/profiling/pyroscope.yaml`: Monolithic deployment in `argus-system` with dedicated PVC, air-gapped image mirror (`localhost:5001/argus/pyroscope:1.7.1`), usage reporting disabled.
  - Verification & Edge Cases:
      * `scripts/test-profiling.sh` + `scripts/test-profiling-edge-cases.sh`: Ingested folded and pprof stack traces, verified FlameQL render API returning CPU and memory flame graphs. Evidence in `.harness/evidence/F010/`.
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)

## 2026-10-14 — F009 Infrastructure Metrics via node-exporter & kube-state-metrics — COMPLETE
Branch/commit: main @ 3a4a000   PR: N/A   CI: green
Evidence:
  - Deployment & Pipelines:
      * `deploy/infra-metrics/node-exporter.yaml` (DaemonSet) and `deploy/infra-metrics/kube-state-metrics.yaml` (Deployment) using air-gapped mirror images.
      * OTel node scraper and gateway scraping pipelines routing metrics into ClickHouse and SigNoz.
  - Verification & Edge Cases:
      * `scripts/test-infra-metrics.sh` + `scripts/test-infra-metrics-edge-cases.sh`: 100% green verification across node and cluster metrics. Evidence in `.harness/evidence/F009/`.
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)

Branch/commit: chore/parallel-execution-harness   PR: N/A   CI: green
Evidence:
  - Architecture Specification:
      * `.harness/PARALLEL_EXECUTION_GRAPH.md` stood up defining 5 Execution Tracks (Tracks A-E), 5 Waves, and hard Synchronization Gates (G1-G5).
      * Complete 21-Feature Dependency Matrix (F001-F021) with execution mode, prerequisites, concurrent candidates, and downstream blockers.
      * Conflict & Concurrency Analysis: Port collisions (zero), Kubernetes resource/CRD write locks (zero), ClickHouse schema/MV locks (zero).
      * Multi-Agent Subagent Execution Protocol: Orchestrator dispatching parallel subagents across tracks and enforcing barrier waits at synchronization gates.
  - Tracking & Phase Updates:
      * `ROADMAP.md` updated to 8/21 COMPLETE (38%) with explicit `[SEQUENTIAL GATE]` and `[PARALLEL TRACK X]` annotations for all 21 features.
      * `PROJECT_STATE.md` and `CURRENT_TASK.md` updated with active Wave 2 parallel dispatch packages (F009 || F010 || F011 || F014).
      * `PHASE-02-COVERAGE.md`, `PHASE-03-OPERATIONAL.md`, `PHASE-04-FRONTEND-SIGNALS.md`, `PHASE-05-AIOPS.md`, and `rules/scope-guard.md` aligned with the parallel graph.

## 2026-10-13 — F008 eBPF Safety Net (Beyla) — COMPLETE
Branch/commit: feat/F008   PR: N/A   CI: green
Evidence:
  - Architecture Decision:
      * `docs/decisions/ADR-0005-ebpf-safety-net-beyla.md` (and `.harness/architecture/decisions/ADR-0005-ebpf-safety-net-beyla.md`) evaluating Grafana Beyla vs Pixie for kernel-level service map floor.
  - Air-gapped Image Mirroring:
      * `grafana/beyla:2.2.4` mirrored to `localhost:5001/argus/beyla:2.2.4` in `deploy/mirror/images.txt`.
  - Deployment & DaemonSet:
      * `deploy/ebpf/beyla.yaml` deployed in `argus-system` with BPF capabilities (`SYS_ADMIN`, `SYS_PTRACE`, `NET_ADMIN`) and OpenTelemetry exporter targeting the gateway.
  - Test Suites & Full Verification:
      * `./scripts/test-ebpf.sh` and `./scripts/test-ebpf-edge-cases.sh` created and integrated into `./scripts/verify.sh` (17-step full suite green).
      * Evidence captured under `.harness/evidence/F008/` (`signoz-services-ebpf.json`, `edge-cases-output.txt`).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: F008 is COMPLETE! Wave 1 is 100% complete (8/21 features). Unlocks Wave 2 parallel dispatch.

## 2026-10-13 — F007 Zero-Code Auto-Instrumentation & Service Onboarding Runbook — COMPLETE
Branch/commit: feat/F007   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - Air-gapped Mirror Registry:
      * `ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-python:0.65b0` -> `localhost:5001/argus/autoinstrumentation-python:0.65b0`
      * `ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-nodejs:0.78.0` -> `localhost:5001/argus/autoinstrumentation-nodejs:0.78.0`
      * `ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:2` -> `localhost:5001/argus/autoinstrumentation-java:2`
      * `localhost:5001/argus/auto-service:1.0.0` (un-instrumented sample python microservice)
  - Declarative Instrumentation Custom Resource:
      * `deploy/otel/instrumentation.yaml` configured in `argus-system` and `default`.
      * Targets gateway exporter at `http://argus-gateway-collector.argus-system.svc.cluster.local:4318`.
      * Injects safe resource limits (100m CPU, 128Mi RAM) and w3c tracecontext/baggage propagators.
  - Zero-Code Onboarding Runbook & Microservice:
      * `docs/runbooks/service-onboarding.md` (one-line copy-paste guide for Python, Node.js, Java workloads with verification and troubleshooting steps).
      * `deploy/sample-app/auto-instrumented-service.yaml` and `deploy/sample-app/auto-app/` with annotation `instrumentation.opentelemetry.io/inject-python: "true"`.
  - Functional Tests & Evidence:
      * `./scripts/test-auto-instrumentation.sh` -> PASS (7/7 steps: validated CR, verified mutating webhook injection of init-container and PYTHONPATH, generated synthetic HTTP transaction, verified 4 auto-instrumented spans in ClickHouse `signoz_traces.signoz_index_v3` with Trace ID, verified service discovery in SigNoz `/api/v1/services/list`, and retrieved trace by Trace ID via SigNoz API).
      * `./scripts/test-auto-instrumentation-edge-cases.sh` -> PASS (5/5 edge cases: unsupported language annotation safely ignored, annotation typo ignored, init-container resource limits strictly enforced, workload resilience during collector downtime verified HTTP 200 without blocking or crashing, multi-namespace injection in `default` verified with air-gapped image).
      * `./scripts/verify.sh` -> PASS: 15/15 verification steps green.
      * Evidence captured in `.harness/evidence/F007/` (`injected-pod-spec.json`, `clickhouse-auto-spans.json`, `signoz-services-list.json`, `signoz-auto-trace.json`, `edge-cases-output.txt`).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: F007 is COMPLETE! Transitioning to F008 (eBPF safety net via Beyla for network-level service map).

## 2026-10-12 — F006 SigNoz UI over ClickHouse HA — COMPLETE
Branch/commit: feat/F006   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - Air-gapped Mirror Registry:
      * `signoz/signoz:v0.145.0` -> `localhost:5001/argus/signoz:v0.145.0`
      * `signoz/signoz-otel-collector:v0.144.13` -> `localhost:5001/argus/signoz-otel-collector:v0.144.13`
      * `clickhouse/clickhouse-server:25.12.5` -> `localhost:5001/argus/clickhouse-server:25.12.5`
  - ClickHouse HA & Migrations:
      * Upgraded ClickHouse HA to `25.12.5` with `allow_experimental_json_type: 1` and `allow_experimental_object_type: 1` to support SigNoz v0.145.0 schema settings (`object_serialization_version = 'v3'`).
      * Configured `<cluster>` cluster alias in remote_servers without hyphens and inter-node credentials (`default:argus123`).
      * Applied full SigNoz schema migrations: `migrate ready`, `migrate bootstrap`, `migrate sync up`, `migrate async up` (created `signoz_traces.signoz_index_v3`, `signoz_logs.logs_v2`, `signoz_metrics.samples_v4`, etc.).
  - Declarative Deployment & Pipelines:
      * `deploy/signoz/signoz-otel-collector.yaml` (OTel collector with ClickHouse exporters).
      * `deploy/signoz/signoz.yaml` (SigNoz UI and Query Server on port 8080).
      * `deploy/otel/gateway.yaml` forwarding redacted telemetry to `signoz-otel-collector:4317`.
  - Functional Tests & Evidence:
      * `./scripts/test-signoz.sh` -> PASS (Service discovery found `argus-sample-service`, Trace query returned `process_order` span by TraceId, Unified query returned logs, boot settings verified PostHog/Appcues/Sentry/Pylon disabled, zero external socket connections).
      * `./scripts/test-signoz-edge-cases.sh` -> 4 passed, 0 failed (Empty-state queries handled without 500 panic, 401 unauthenticated rejected cleanly, query SLA < 5s met, ClickHouse upstream error handled without crashing, restart count remained 0).
      * `./scripts/verify.sh` -> PASS: 13/13 verification steps green.
      * Evidence captured in `.harness/evidence/F006/` (`signoz-version.json`, `signoz-health.json`, `signoz-services.json`, `signoz-trace.json`, `signoz-logs-query.json`, `signoz-boot-settings.json`, `air-gap-audit.txt`).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: F006 is COMPLETE! Next feature is F007 (Zero-code auto-instrumentation via OTel Operator annotation + onboarding runbook for app teams).

## 2026-10-12 — F005 PII/CJIS redaction at ingest — COMPLETE
Branch/commit: feat/F005   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - Declarative Redaction Processor in OpenTelemetry Gateway:
      * `deploy/otel/gateway.yaml` configured with `transform/redaction` OTTL processor.
      * Strips agreed compliance blacklist keys: `password`, `token`, `auth_token`, `secret`, `api_key`, `cjis_fbi_number`, `ssn`, `credit_card`.
      * Masks unstructured PII: SSN regex `\b\d{3}-\d{2}-\d{4}\b` -> `[REDACTED_SSN]`, Credit Card (PAN) regex `\b(?:\d[ -]*?){13,16}\b` -> `[REDACTED_PAN]`.
      * Masks inline key-value credentials in log bodies: `(?i)(password|secret|token|auth_token|api_key|cjis_fbi_number|ssn)=[^&\s,;]+` -> `$$1=[REDACTED]`.
      * Applies across all telemetry signals: traces (span attributes), span events (`Events.Attributes`), and logs (`LogAttributes`, `Body`).
  - `./scripts/test-redaction.sh` -> PASS:
      * Injected sensitive SSN, passwords, bearer tokens, CJIS FBI identifiers, and credit cards into trace span attributes, span events, log attributes, and log body.
      * ClickHouse SQL queries assert sensitive keys stripped and freeform values masked.
      * Global database scan proves 0 sensitive records exist across `default.otel_traces` and `default.otel_logs`.
  - `./scripts/test-redaction-edge-cases.sh` -> 4 passed, 0 failed:
      * Multiple PII instances in a single log body: all occurrences scrubbed to `[REDACTED_SSN]` and `[REDACTED_PAN]`.
      * Concurrent body and attribute secret scrubbing verified.
      * Mixed attribute data types (bool, int, double, empty string) safely handled without collector panic.
      * Live sample service transaction passes cleanly through redaction pipeline.
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of pods run from `localhost:5001/argus/*` (air-gap compliant).
  - `./scripts/verify.sh` -> PASS: full 11-step verification suite green (Architecture + Edge cases + ClickHouse tiering + ClickHouse edge cases + OTel pipeline + OTel edge cases + Telemetry correlation + Correlation edge cases + Redaction verification + Redaction edge cases + Baseline readiness).
  - e2e: Correlated request with PII verified end to end (Phase 01 smoke test passed).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Phase 01 (Foundation) is 100% COMPLETE! All 5 foundation features (F001-F005) verified and green. Moving to Phase 02 (Coverage), beginning with F006 (SigNoz deployment).

## 2026-10-12 — F004 End-to-end correlation proof — COMPLETE
Branch/commit: feat/F004   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - `./deploy/mirror/images.txt` & `./deploy/mirror/setup-mirror.sh` -> Mirrored verified base & sample images:
      * `python:3.12-alpine` to `localhost:5001/argus/python:3.12-alpine`
      * `localhost:5001/argus/sample-service:1.0.0` (zero-dependency synthetic microservice emitting W3C TraceContext traces, logs, and metrics with exemplars)
  - `deploy/sample-app/app/server.py` & `deploy/sample-app/sample-service.yaml`:
      * Deployed instrumented sample service (`argus-sample-service`) in `argus-system`.
      * Emits correlated OTLP traces (`/v1/traces`), logs (`/v1/logs`), and metrics (`/v1/metrics`) to `http://argus-gateway-collector.argus-system:4318`.
  - Schema upgrade: `deploy/clickhouse/otel-schema.sql` upgraded tables (`otel_traces`, `otel_logs`, `otel_metrics_*`) to `ReplicatedMergeTree('/clickhouse/tables/{shard}/default/...', '{replica}')` backed by ClickHouse Keeper for active-active multi-replica HA.
  - `./scripts/test-correlation.sh` -> PASS:
      * Live HTTP transaction issued to `argus-sample-service`.
      * Single transaction emitted trace span, log record, and metric data point sharing identical W3C `TraceId`.
      * 3-way SQL join query in ClickHouse (`otel_traces` + `otel_logs` + `otel_metrics_gauge` ON `TraceId`) executed and returned correlated record.
      * End-to-end latency from emission to queryable join measured at 2 seconds (well within < 10s SLA).
  - `./scripts/test-correlation-edge-cases.sh` -> 4 passed, 0 failed:
      * Dropped span handling: request with `?drop_span=true` leaves zero traces, while log and metric persist and correlate gracefully without crashing.
      * Log without TraceId: request with `?no_trace_id=true` records log with empty TraceId without parser or ingestion failure.
      * Clock skew handling: telemetry with ±120s timestamp offset accurately ingested and correlated across ClickHouse tables.
      * Pod restart resilience: sample service pod termination and replacement pod recovery maintains clean telemetry emission.
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of pods run from `localhost:5001/argus/*` (air-gap compliant).
  - `./scripts/verify.sh` -> PASS: full 9-step verification suite green (Architecture + Platform edge cases + ClickHouse tiering + ClickHouse edge cases + OTel pipeline + OTel edge cases + Telemetry correlation + Correlation edge cases + Baseline readiness).
  - e2e: Trace verified (`scripts/test-correlation.sh` proves end-to-end trace-metric-log correlation across OpenTelemetry and ClickHouse).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Observability spine is proven end-to-end. F005 (PII/CJIS redaction processor) is next.

## 2026-10-12 — F003 OTel Collector pipeline (ingest spine) — COMPLETE
Branch/commit: feat/F003   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - `./deploy/mirror/images.txt` & `./deploy/mirror/setup-mirror.sh` -> Mirrored verified container image:
      * `otel/opentelemetry-collector-contrib:0.160.0` to `localhost:5001/argus/opentelemetry-collector-contrib:0.160.0` (validated ClickHouse exporter, k8sattributes, kubeletstats, and filelog receivers).
  - Declarative Kubernetes OpenTelemetryCollector manifests:
      * `deploy/otel/rbac.yaml`: ServiceAccount `argus-collector`, ClusterRole, ClusterRoleBinding for pod, node, namespace metadata inspection.
      * `deploy/clickhouse/otel-schema.sql`: Pre-created DDL schemas for `otel_traces`, `otel_logs`, `otel_metrics_*` on ClickHouse HA replicas.
      * `deploy/otel/gateway.yaml`: Gateway Deployment collector exposing OTLP gRPC (4317) and HTTP (4318), memory_limiter, k8sattributes enrichment, batch processor, and clickhouse exporter.
      * `deploy/otel/node-daemonset.yaml`: Node DaemonSet collector with `kubeletstats`, `filelog` container log scraper, and OTLP receiver forwarding to the gateway.
  - `./scripts/deploy-otel.sh` -> Deployed gateway and node DaemonSet; both rolled out successfully.
  - `./scripts/test-otel-pipeline.sh` -> 5 passed, 0 failed:
      * Gateway & Node DaemonSet readiness verified.
      * OTLP trace ingestion verified; landed in `otel_traces` with `k8s.namespace.name` and `k8s.node.name`.
      * OTLP metric ingestion verified; landed in `otel_metrics_gauge` with `k8s.*` attributes.
      * OTLP log ingestion verified; landed in `otel_logs` with `k8s.*` attributes.
      * Continuous node-level scraping verified (cluster container logs and kubelet stats actively ingesting).
  - `./scripts/test-otel-edge-cases.sh` -> 4 passed, 0 failed:
      * Malformed OTLP trace JSON rejected with HTTP 400 without crashing gateway.
      * Gateway remains healthy and accepting traffic after malformed input.
      * Node DaemonSet pod kill clean recovery without filelock crash loops.
      * Gateway deployment rollout restart preserves connectivity and accepts immediate OTLP traffic.
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of collector pods run from `localhost:5001/argus/*`.
  - `./scripts/verify.sh` -> PASS: full 7-step verification suite green (Architecture + Edge cases + ClickHouse tiering + ClickHouse edge cases + OTel pipeline + OTel edge cases + Baseline readiness).
  - e2e: N/A — not user-facing (ingestion spine proven; end-to-end trace-metric-log correlation proven in F004).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Ingest pipeline is live and ready for end-to-end correlation proof (F004).

## 2026-10-12 — F002 ClickHouse HA + object-storage tier — COMPLETE
Branch/commit: feat/F002   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - `./deploy/mirror/images.txt` & `./deploy/mirror/setup-mirror.sh` -> Mirrored verified container images:
      * `clickhouse/clickhouse-server:24.8.4.13`
      * `clickhouse/clickhouse-keeper:latest`
      * `chrislusf/seaweedfs:latest`
  - `./scripts/deploy-clickhouse.sh` -> Declarative rollout of storage stack into `argus-system`:
      * `deploy/storage/s3-storage.yaml` (SeaweedFS S3-compatible cold tier with persistent PVC `argus-s3-pvc`)
      * `deploy/clickhouse/clickhouse-keeper.yaml` (ClickHouse Keeper cluster for distributed coordination)
      * `deploy/clickhouse/clickhouse-ha.yaml` (ClickHouseInstallation with 2 replicas, tiered storage policy `tiered_hot_cold`)
  - `./scripts/test-clickhouse-tiering.sh` -> PASS:
      * 2-node HA cluster topology verified in `system.clusters`
      * Storage disks `default` (local hot) and `s3_cold` (object storage) verified in `system.disks`
      * Tiered storage movement verified: part moved from `default` to `s3_cold`, rows readable transparently via S3 cold tier
      * Pod restart resilience verified: canary row preserved across pod kill and restart (zero data loss)
  - `./scripts/test-clickhouse-edge-cases.sh` -> 3 passed, 0 failed:
      * Surviving replica serves reads independently during single-node failover
      * Writes land on local hot disk first, unaffected by remote object store
      * Distributed data replication across replicas via ClickHouse Keeper
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of ClickHouse, Keeper, and S3 pods run from `localhost:5001/argus/*`.
  - `./scripts/verify.sh` -> PASS: full 5-step verification suite green (Architecture + Platform edge cases + ClickHouse tiering + ClickHouse edge cases + Baseline readiness).
  - e2e: N/A — not user-facing (backend data tier verified by automated SQL test suite).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Storage tier is ready for OTel Collector pipeline (F003) to ingest metrics, logs, and traces.

## 2026-10-12 — F001 Cluster baseline + operators — COMPLETE
Branch/commit: feat/F001   PR: N/A (local gitops repo, no remote origin configured)   CI: green
Evidence:
  - `./deploy/mirror/setup-mirror.sh` -> Initialized local OCI mirror registry `localhost:5001`, populated with latest verified container images:
      * `ghcr.io/open-telemetry/opentelemetry-operator/opentelemetry-operator:0.160.0`
      * `ghcr.io/open-telemetry/opentelemetry-collector-releases/opentelemetry-collector-k8s:0.160.0`
      * `altinity/clickhouse-operator:0.27.4`
      * `altinity/metrics-exporter:0.27.4`
      * `quay.io/prometheus-operator/prometheus-operator:v0.94.1`
      * `quay.io/prometheus-operator/prometheus-config-reloader:v0.94.1`
      * `quay.io/prometheus-operator/admission-webhook:v0.94.1`
      * `ghcr.io/jkroepke/kube-webhook-certgen:1.8.9`
  - `./scripts/deploy-operators.sh` -> Declarative Helm GitOps deployments into `argus-system`:
      * `opentelemetry-operator` (chart 0.124.1, app 0.160.0)
      * `altinity-clickhouse-operator` (chart 0.27.4, app 0.27.4)
      * `prometheus-operator` (chart 92.3.0, app v0.94.1)
  - `kubectl get pods -n argus-system -o jsonpath='...'` -> Confirms 100% of running container images resolve strictly from `localhost:5001/argus/...` (air-gap compliant, zero public registry pulls).
  - `./scripts/test-edge-cases.sh` -> 4 passed, 0 failed (unreachable mirror fast-fail, missing namespace/CRDs detection, check-architecture permissive no-op).
  - `./scripts/init.sh` -> PASS: validates cluster connectivity, mirror health, CRD existence, operator readiness, and image origins.
  - `./scripts/verify.sh` -> PASS: full verification suite (architecture + edge cases + init).
  - e2e: N/A — not user-facing (operator infrastructure baseline verified by init smoke and controller readiness).
Evaluator: acceptance=5 correctness=5 boundaries=5 modularity=5 evidence=5 => avg 5.0 (PASS)
Notes: Operators are ready to support Phase 01 features. F002 (ClickHouse HA) is next.
