# Project Argus

> **Self-Hosted, Air-Gapped Kubernetes Observability Platform for DHS**  
> *Telemetry Spine: OpenTelemetry Collector → ClickHouse HA → SigNoz APM*

[![Status](https://img.shields.io/badge/Progress-8%20%2F%2021%20Features%20(38.1%25)-green.svg)](#roadmap--delivery-status)
[![Compliance](https://img.shields.io/badge/Air--Gap-100%25%20Offline%20Mirror-blue.svg)](#air-gap-strictness--mirror-management)
[![Security](https://img.shields.io/badge/Ingest-CJIS%20%2F%20PII%20Redacted-orange.svg)](#ingest-security--cjispii-redaction)
[![Verification](https://img.shields.io/badge/Regression-17%20%2F%2017%20Suites%20Passing-brightgreen.svg)](#verification--quality-assurance)

Project Argus is an enterprise-grade, internal DHS observability platform engineered to provide Datadog-equivalent telemetry (distributed tracing, application performance monitoring, logs, infrastructure metrics, and eBPF network maps) running entirely on air-gapped internal Kubernetes clusters with zero external SaaS egress.

---

## Architecture & Telemetry Spine

```
                          ┌──────────────────────────────────────────────┐
                          │         Kubernetes Workload Clusters         │
                          └──────────────────────┬───────────────────────┘
                                                 │
                  ┌──────────────────────────────┴──────────────────────────────┐
                  ▼                                                             ▼
     [Auto-Instrumented Pods]                                      [Un-Annotated Workloads]
  (Python, Java, Node.js via CRD)                                  (Raw HTTP/gRPC Services)
                  │                                                             │
                  │ OTLP / gRPC                                                 │ Linux Sockets
                  ▼                                                             ▼
     ┌───────────────────────────┐                                 ┌─────────────────────────┐
     │   argus-node-collector    │                                 │       argus-beyla       │
     │     (OTel DaemonSet)      │                                 │     (eBPF DaemonSet)    │
     └─────────────┬─────────────┘                                 └────────────┬────────────┘
                   │                                                            │
                   └─────────────────────────────┬──────────────────────────────┘
                                                 ▼ OTLP (4317 / 4318)
                                  ┌─────────────────────────────┐
                                  │   argus-gateway-collector   │
                                  │       (OTel Gateway)        │
                                  └──────────────┬──────────────┘
                                                 │
                                                 │ 1. K8s Metadata Enrichment
                                                 │ 2. CJIS / PII Redaction at Ingest
                                                 │ 3. Memory-Bounded Micro-Batching
                                                 │
                         ┌───────────────────────┴───────────────────────┐
                         ▼                                               ▼
          ┌─────────────────────────────┐                 ┌─────────────────────────────┐
          │     ClickHouse HA Cluster   │                 │     SigNoz APM Collector    │
          │  (2-Node Replicated Cluster)│                 │     & Query Engine (UI)     │
          └──────────────┬──────────────┘                 └─────────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────────┐
          │      MinIO / S3 Storage     │
          │    (Tiered Cold Storage)    │
          └─────────────────────────────┘
```

### Core Architecture Pillars

1. **Deterministic Ingest Pipeline**: [`argus-gateway-collector`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/otel/gateway.yaml) functions as the central telemetry gateway, enforcing Kubernetes metadata decoration (`k8sattributes`), in-memory PII/CJIS redaction, and backpressure handling.
2. **Deterministic Redaction**: PII and CJIS identifiers (SSNs, credit cards, FBI numbers, authorization tokens, passwords) are scrubbed in-memory via regex transform processors before reaching persistent storage.
3. **High-Availability Storage**: ClickHouse HA (`argus-cluster`, 2 shards/replicas) backed by automated cold tiering to S3/MinIO (`hot_to_cold` policy) with ClickHouse Keeper Raft consensus.
4. **Dual-Layer Observability Onboarding**:
   - **Zero-Code Instrumentation**: Workloads are auto-instrumented via a single Kubernetes annotation (`instrumentation.opentelemetry.io/inject-python: "true"`).
   - **eBPF Safety Net**: Grafana Beyla provides zero-overhead network-level service discovery and RED metrics (Rate, Errors, Duration) for un-annotated or third-party workloads.
5. **Air-Gap Strictness**: 100% of container images and Helm charts resolve from the local offline registry mirror (`localhost:5001/argus/*`).

---

## Roadmap & Delivery Status

Progress: **8 / 21 Features Complete (38.1%)** across 5 Phases.

| Feature ID | Title | Phase | Execution Mode | Track | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **F001** | Cluster Baseline & Air-Gapped Operators | Phase 01 | Sequential Gate | Gate 1 | **COMPLETE** |
| **F002** | ClickHouse HA (2-node + S3 Storage Policy) | Phase 01 | Sequential Gate | Gate 1 | **COMPLETE** |
| **F003** | OTel Collector Pipeline (DaemonSet + Gateway) | Phase 01 | Sequential Gate | Gate 1 | **COMPLETE** |
| **F004** | 3-Way Trace + Metric + Log Correlation | Phase 01 | Sequential Gate | Gate 1 | **COMPLETE** |
| **F005** | Ingest PII & CJIS Redaction Processor | Phase 01 | Sequential Gate | Gate 1 | **COMPLETE** |
| **F006** | SigNoz APM UI & ClickHouse Analytics | Phase 02 | Sequential Gate | Gate 2 | **COMPLETE** |
| **F007** | Zero-Code Auto-Instrumentation & Runbook | Phase 02 | Concurrent | Track A | **COMPLETE** |
| **F008** | eBPF Safety Net (Beyla Service Map Floor) | Phase 02 | Concurrent | Track A | **COMPLETE** |
| **F009** | Infra Metrics (node-exporter + KSM) | Phase 02 | Concurrent | Track A | *NEXT* |
| **F010** | Continuous Profiling (Pyroscope) | Phase 02 | Concurrent | Track A | *BACKLOG* |
| **F011** | Alerting / Monitors (Firing-State + Dedup) | Phase 03 | Concurrent | Track B | *BACKLOG* |
| **F012** | SLO Tracking & Error Budgets | Phase 03 | Concurrent | Track B | *BACKLOG* |
| **F013** | Paging Path (ServiceNow Incident Webhook) | Phase 03 | Concurrent | Track B | *BACKLOG* |
| **F014** | Retention, Downsampling & Log-Level Filters | Phase 03 | Concurrent | Track C | *BACKLOG* |
| **F015** | Multi-Tenancy & Cardinality Guardrails | Phase 03 | Concurrent | Track C | *BACKLOG* |
| **F016** | SSO / RBAC via Agency IdP (SAML/OIDC/PIV) | Phase 03 | Sequential Gate | Track C | *BACKLOG* |
| **F017** | RUM & DOM Session Replay (HyperDX/OpenReplay)| Phase 04 | Concurrent | Track D | *BACKLOG* |
| **F018** | Synthetics (Playwright CronJobs + Probes) | Phase 04 | Sequential Gate | Track D | *BACKLOG* |
| **F019** | Anomaly & Forecast Monitors (EWMA/STL) | Phase 05 | Sequential Gate | Track E | *BACKLOG* |
| **F020** | Alert Correlation & Root-Cause Grouping | Phase 05 | Sequential Gate | Track E | *BACKLOG* |
| **F021** | NL Query & Incident Brief Copilot (Bedrock) | Phase 05 | Sequential Gate | Track E | *BACKLOG* |

---

## Parallel Execution Topology

Project Argus is structured into **5 Concurrent Execution Tracks** bounded by **5 Hard Synchronization Gates** to enable safe, multi-agent parallel execution without port collisions, CRD race conditions, or database deadlocks:

```
[Wave 1: Foundation (F001-F005)] ─────────────────────────> COMPLETE (Gate G1)
             │
[Wave 2: Coverage Closeout & Platform Metrics]
 ├── Track A1: F007 (Auto-Instrumentation) ──────────────> COMPLETE
 ├── Track A2: F008 (eBPF Safety Net) ───────────────────> COMPLETE
 ├── Track A3: F009 (Infra Metrics: node-exporter/KSM) ──> IN PROGRESS
 └── Track A4: F010 (Continuous Profiling: Pyroscope) ───> READY
             │
 ════════════╪═════════════════════════════════════════════ [SYNC GATE G2]
             │
[Wave 3: Operational & Governance Acceleration]
 ├── Track B (Operations):   F011 (Monitors) ──> F012 (SLOs) || F013 (Paging)
 └── Track C (Governance):   F014 (Retention) || F015 (Multi-Tenancy) ──> F016 (SSO)
             │
 ════════════╪═════════════════════════════════════════════ [SYNC GATE G3]
             │
[Wave 4: Frontend Signals & Synthetic Probes]
 └── Track D (Frontend):     F017 (RUM & Replay) || F018 (Synthetics)
             │
 ════════════╪═════════════════════════════════════════════ [SYNC GATE G4]
             │
[Wave 5: Autonomous AIOps & Intelligence Moat]
 └── Track E (AIOps):        F019 (Anomaly) ──> F020 (Correlation) ──> F021 (Copilot)
             │
 ════════════╪═════════════════════════════════════════════ [FINAL GATE G5: PROD READY]
```

### Execution Tracks Summary
- **Track A (Metric & Signal Collection)**: F007, F008, F009, F010
- **Track B (Incident & Operational Lifecycle)**: F011, F012, F013
- **Track C (Data Governance, Storage & Security)**: F014, F015, F016
- **Track D (Frontend & Synthetic Monitoring)**: F017, F018
- **Track E (AIOps & LLM Intelligence)**: F019, F020, F021

For the complete dependency matrix, conflict analysis, and subagent orchestration instructions, see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md).

---

## Service Onboarding Guide

Argus provides two distinct, complementary onboarding strategies to achieve 100% observability across workloads:

### Strategy A: Zero-Code Auto-Instrumentation (Application Layer)

Ideal for microservices built on standard runtimes (Python, Java, Node.js). Telemetry agents are injected automatically at pod creation time via the OpenTelemetry Mutating Admission Webhook.

Add a single annotation to your `spec.template.metadata.annotations`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: default
spec:
  replicas: 1
  template:
    metadata:
      annotations:
        # Injects OTel Agent, SDK configuration, and OTLP endpoint:
        instrumentation.opentelemetry.io/inject-python: "true"
      labels:
        app: order-service
    spec:
      containers:
        - name: app
          image: localhost:5001/argus/sample-python-app:latest
          ports:
            - containerPort: 8080
```

Supported Annotations:
- **Python**: `instrumentation.opentelemetry.io/inject-python: "true"`
- **Java**: `instrumentation.opentelemetry.io/inject-java: "true"`
- **Node.js**: `instrumentation.opentelemetry.io/inject-nodejs: "true"`

For end-to-end guidance, see [`docs/runbooks/service-onboarding.md`](file:///Users/nimatullahrazmjo/workstation/argus/docs/runbooks/service-onboarding.md).

### Strategy B: eBPF Safety Net (Kernel Socket Layer)

Ideal for legacy services, compiled binaries (Go, Rust, C++), third-party COTS containers, or un-annotated workloads. 

Grafana Beyla runs as a lightweight DaemonSet ([`deploy/ebpf/beyla.yaml`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/ebpf/beyla.yaml)), attaching eBPF probes directly to Linux socket syscalls (`kprobe`/`uprobe`). It automatically discovers active HTTP/gRPC services without requiring code modification, restarts, or pod annotations:
- Emits RED metrics (`http_server_request_duration_seconds`, error rates, call counts).
- Emits network-level L7 distributed traces to `argus-gateway-collector:4318`.
- CPU overhead is bounded strictly to < 5% per node with < 256Mi RAM footprint.

---

## Ingest Security & CJIS/PII Redaction

Argus operates under strict FedRAMP High and CJIS compliance mandates. All incoming telemetry spans and log records pass through the gateway transform processor before being written to disk:

1. **CJIS FBI Numbers**: Pattern `\b[0-9]{7}[A-Z0-9]{2}\b` masked to `[REDACTED_CJIS_FBI_NUMBER]`.
2. **Social Security Numbers (SSN)**: Pattern `\b\d{3}-\d{2}-\d{4}\b` masked to `[REDACTED_SSN]`.
3. **Payment Cards (PAN)**: 13-to-19 digit card numbers masked to `[REDACTED_CREDIT_CARD]`.
4. **Authentication Credentials**: Bearer tokens, Authorization headers, and password parameters masked to `[REDACTED_CREDENTIAL]`.

Verification: Covered by [`scripts/test-redaction.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-redaction.sh) and [`scripts/test-redaction-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-redaction-edge-cases.sh).

---

## High Availability & Storage Tiering

The Argus storage spine uses ClickHouse HA deployed via the Altinity ClickHouse Operator:

- **Topology**: 2-Node Replicated Cluster (`chi-argus-clickhouse-argus-cluster-0-0-0` and `...-0-1-0`).
- **Consensus**: ClickHouse Keeper with 3-node Raft coordination (`deploy/clickhouse/clickhouse-keeper.yaml`).
- **Tiering Policy (`hot_to_cold`)**:
  - Hot tier: Local persistent volume (SSD/NVMe).
  - Cold tier: S3-compatible MinIO object storage (`deploy/storage/s3-storage.yaml`).
  - Automatic migration triggers when hot volume reaches 90% threshold.

---

## Air-Gap Strictness & Mirror Management

Argus forbids runtime egress to public container registries or SaaS endpoints. All container images and artifacts are mirrored locally:

- **Local Mirror**: Docker Registry v2 running at `localhost:5001`.
- **Image Inventory**: Maintained in [`deploy/mirror/images.txt`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/mirror/images.txt).
- **Mirror Sync**: Managed via [`deploy/mirror/setup-mirror.sh`](file:///Users/nimatullahrazmjo/workstation/argus/deploy/mirror/setup-mirror.sh).

Every Kubernetes manifest references `localhost:5001/argus/<image>:<tag>` directly.

---

## Verification & Quality Assurance

Argus enforces a strict test-driven harness contract. No feature is marked complete without green verification across both functional tests and comprehensive edge-case batteries:

```bash
# Execute the full 17-step end-to-end regression suite
./scripts/verify.sh
```

### Full Verification Battery

| Step | Verification Suite | Target Component / Feature |
| :--- | :--- | :--- |
| **1** | [`scripts/check-architecture.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/check-architecture.sh) | Architectural Layer Boundaries & Namespace Separation |
| **2** | [`scripts/test-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-edge-cases.sh) | Core Platform Failure Resilience & Crash Recovery |
| **3** | [`scripts/test-clickhouse-tiering.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-clickhouse-tiering.sh) | ClickHouse HA, S3 Disk Tiering & Node Restarts |
| **4** | [`scripts/test-clickhouse-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-clickhouse-edge-cases.sh) | Keeper Consensus Loss, Partition Recovery & Table Replication |
| **5** | [`scripts/test-otel-pipeline.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-otel-pipeline.sh) | OTel Collector DaemonSet & Gateway Ingest Routing |
| **6** | [`scripts/test-otel-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-otel-edge-cases.sh) | Buffer Overflow, Gateway Backpressure & Network Partitions |
| **7** | [`scripts/test-correlation.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-correlation.sh) | 3-Way TraceId Join (Distributed Traces, Metrics, Logs) |
| **8** | [`scripts/test-correlation-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-correlation-edge-cases.sh) | Missing TraceContext, Malformed Spans & Clock Skew |
| **9** | [`scripts/test-redaction.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-redaction.sh) | In-Memory PII & CJIS Redaction Validation |
| **10** | [`scripts/test-redaction-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-redaction-edge-cases.sh) | Boundary Regex Evasion, Unicode Bypasses & Large Payloads |
| **11** | [`scripts/test-signoz.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-signoz.sh) | SigNoz APM UI, ClickHouse Analytical Engine & Queries |
| **12** | [`scripts/test-signoz-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-signoz-edge-cases.sh) | Cold Start Resilience & ClickHouse Partition Degradation |
| **13** | [`scripts/test-auto-instrumentation.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-auto-instrumentation.sh) | F007 Zero-Code Webhook Auto-Injection E2E |
| **14** | [`scripts/test-auto-instrumentation-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-auto-instrumentation-edge-cases.sh) | Unsupported Runtimes, Annotation Typos & Memory Clamping |
| **15** | [`scripts/test-ebpf.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-ebpf.sh) | F008 eBPF Safety Net Discovery & RED Metric Export |
| **16** | [`scripts/test-ebpf-edge-cases.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/test-ebpf-edge-cases.sh) | Kernel Safety, Zero-Egress Audit & Pod Churn Resilience |
| **17** | [`scripts/init.sh`](file:///Users/nimatullahrazmjo/workstation/argus/scripts/init.sh) | Baseline Air-Gap Cluster Readiness Audit |

---

## Repository Structure

```
argus/
├── .harness/                  # Project tracking harness (specs, state, roadmap, graph)
│   ├── PARALLEL_EXECUTION_GRAPH.md  # Master parallel dependency matrix & track topology
│   ├── ROADMAP.md             # Feature scope, prerequisites & status
│   ├── PROJECT_STATE.md       # Master state & active wave overview
│   ├── CURRENT_TASK.md        # Current sprint focus and immediate next actions
│   ├── DECISIONS.md           # Architecture Decision Record (ADR) index
│   └── phases/                # Acceptance criteria per phase (01 through 05)
├── deploy/                    # Declarative Kubernetes manifests
│   ├── clickhouse/            # ClickHouse HA, Keeper & OTel schema DDL
│   ├── ebpf/                  # Grafana Beyla DaemonSet, ConfigMap & RBAC
│   ├── mirror/                # Air-gapped registry catalog & sync scripts
│   ├── otel/                  # OpenTelemetry collector DaemonSet, Gateway & CRDs
│   ├── sample-app/            # Test microservices (sample & auto-instrumented)
│   ├── signoz/                # SigNoz APM query service, UI & schema migration
│   └── storage/               # MinIO S3 cold storage tier manifests
├── docs/                      # Technical documentation & operational runbooks
│   ├── decisions/             # Architecture Decision Records (ADRs)
│   └── runbooks/              # Service onboarding runbooks
└── scripts/                   # Automated operations & verification test suites
    ├── init.sh                # Baseline cluster readiness check
    ├── verify.sh              # Full 17-step end-to-end regression suite
    ├── test-auto-instrumentation.sh # F007 auto-injection verification
    ├── test-ebpf.sh           # F008 eBPF safety net functional verification
    └── test-ebpf-edge-cases.sh# F008 eBPF edge case & failure battery
```

---

## Quickstart & Local Execution

### 1. Prerequisites
- Docker Desktop or Minikube with Kubernetes v1.28+ enabled.
- Kubernetes context set to active cluster (`kubectl config current-context`).
- Local registry mirror running on `localhost:5001`.

### 2. Initialize Air-Gapped Mirror
```bash
./deploy/mirror/setup-mirror.sh
```

### 3. Deploy Platform Telemetry Spine
```bash
# 1. Operators (OTel Operator, Altinity ClickHouse Operator, Prometheus Operator)
./scripts/deploy-operators.sh

# 2. S3 Storage & ClickHouse HA
./scripts/deploy-clickhouse.sh

# 3. OpenTelemetry Collector Pipeline (DaemonSet + Gateway)
./scripts/deploy-otel.sh

# 4. SigNoz APM UI & Analytics Engine
./scripts/deploy-signoz.sh

# 5. eBPF Safety Net (Grafana Beyla DaemonSet)
kubectl apply -f deploy/ebpf/beyla.yaml
```

### 4. Run Full Verification Suite
```bash
./scripts/verify.sh
```

---

## Troubleshooting & Operational Notes

- **ClickHouse Keeper Startup Timing**: On Docker Desktop, ClickHouse Keeper replays uncompacted Raft changelogs on startup. The Keeper pod includes a dedicated `startupProbe` with a 300-second window (`failureThreshold: 60, periodSeconds: 5`) to prevent premature liveness kills during WAL replay.
- **eBPF Kernel Compatibility**: Beyla requires Linux kernel 5.8+ with BPF subsystem support. Pods require `securityContext.privileged: true` or `CAP_BPF`, `CAP_PERFMON`, `CAP_NET_ADMIN`, and `/sys/kernel/debug` volume mounts.
- **Collector Gateway Ingest**: The gateway listens on port `4317` (gRPC) and `4318` (HTTP). Workloads within `argus-system` or other namespaces route telemetry to `http://argus-gateway-collector.argus-system.svc.cluster.local:4318`.
