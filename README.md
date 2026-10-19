# Project Argus

> **Self-Hosted, Air-Gapped Kubernetes Observability Platform for DHS**
> *Telemetry Spine: OpenTelemetry Collector → ClickHouse HA → SigNoz APM*

[![Status](https://img.shields.io/badge/Progress-21%20%2F%2021%20Features%20Complete-brightgreen.svg)](#roadmap)
[![Compliance](https://img.shields.io/badge/Air--Gap-100%25%20Offline%20Mirror-blue.svg)](#air-gap--mirror-management)
[![Security](https://img.shields.io/badge/Ingest-CJIS%20%2F%20PII%20Redacted-orange.svg)](#ingest-security--cjispii-redaction)
[![Verification](https://img.shields.io/badge/Regression-E2E%20%2B%20Edge%20Suites-brightgreen.svg)](#testing--verification)

Project Argus is an enterprise-grade, internal DHS observability platform engineered to provide Datadog-equivalent telemetry (distributed tracing, application performance monitoring, logs, infrastructure metrics, and eBPF network maps) running entirely on air-gapped internal Kubernetes clusters with zero external SaaS egress.

It spans the full observability lifecycle: a collection spine (OTel → ClickHouse → SigNoz), operations (alerting, SLOs, paging, synthetics, RUM), governance (retention, multi-tenancy, SSO/RBAC), and an in-boundary AIOps layer (anomaly detection, alert correlation, NL-query + incident summarization). A 10-service demo microservice mesh is bundled to generate realistic traffic.

> ⚠️ **Security note:** this is a reference/demo platform. An internal security review found several critical issues (hardcoded JWT secret, unverified tokens, unauthenticated ingest, a stored-XSS replay sink, plaintext DB passwords). See issue [#2](https://github.com/nimatrazmjo/argus/issues/2) before running any of this outside a throwaway local cluster.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Option A — Run a Single Service Locally](#option-a--run-a-single-service-locally-no-cluster)
  - [Option B — One-Command Deploy (deploy.sh / deploy.ps1)](#option-b--one-command-deploy-deploysh--deployps1)
  - [Option C — Helmfile Direct](#option-c--helmfile-direct)
  - [Option D — Manual Step-by-Step Deploy](#option-d--manual-step-by-step-deploy-kubernetes)
- [What Gets Installed](#what-gets-installed)
- [Accessing the Platform](#accessing-the-platform)
- [Sending Telemetry to Argus](#sending-telemetry-to-argus)
- [Services Reference](#services-reference)
- [Service Onboarding](#service-onboarding)
- [Testing & Verification](#testing--verification)
- [Project Structure](#project-structure)
- [Platform Details](#platform-details)
  - [Ingest Security & CJIS/PII Redaction](#ingest-security--cjispii-redaction)
  - [High Availability & Storage Tiering](#high-availability--storage-tiering)
  - [Air-Gap & Mirror Management](#air-gap--mirror-management)
- [Roadmap](#roadmap)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Features

- **Full telemetry spine** — OpenTelemetry collection, ClickHouse HA storage, SigNoz APM UI.
- **Dual onboarding** — zero-code auto-instrumentation (Python/Java/Node) plus an eBPF safety net (Grafana Beyla) for everything else.
- **Operations** — declarative alerting with dedup, SLO/error-budget tracking, ServiceNow paging, synthetic canary probes, and RUM with session replay.
- **Governance** — tiered retention/downsampling, multi-tenancy with row-level isolation, and agency SSO/RBAC with PIV/CAC claims.
- **AIOps** — EWMA/seasonal anomaly + forecast monitors, topological alert correlation, and an in-boundary NL-to-SQL + incident-summary copilot.
- **Air-gapped by design** — 100% offline image mirror, in-memory PII/CJIS redaction at ingest, zero external egress.
- **Dependency-free demo services** — every microservice is a single-file Python 3.12 stdlib server you can run on its own.

---

## Architecture

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

**Core pillars**

1. **Deterministic ingest pipeline** — [`argus-gateway-collector`](deploy/otel/gateway.yaml) is the central telemetry gateway, enforcing Kubernetes metadata decoration (`k8sattributes`), in-memory PII/CJIS redaction, and backpressure handling.
2. **Deterministic redaction** — PII and CJIS identifiers (SSNs, cards, FBI numbers, tokens, passwords) are scrubbed in-memory via regex transform processors before reaching storage.
3. **High-availability storage** — ClickHouse HA (`argus-cluster`, 2 replicas) with automated cold tiering to S3/MinIO (`hot_to_cold`) and ClickHouse Keeper Raft consensus.
4. **Dual-layer onboarding** — zero-code auto-instrumentation via a single annotation, plus a Grafana Beyla eBPF safety net for un-annotated/third-party workloads.
5. **Air-gap strictness** — 100% of images and charts resolve from the local offline mirror (`localhost:5001/argus/*`).

---

## Technology Stack

What each technology is used for, and why it was chosen:

| Layer | Technology | Purpose in Argus |
| :--- | :--- | :--- |
| **Instrumentation** | OpenTelemetry (Operator + SDKs) | Vendor-neutral traces/metrics/logs; zero-code auto-injection into Python/Java/Node pods via a single annotation |
| **Collection** | OTel Collector (DaemonSet + Gateway) | Node-local receive → central gateway for K8s metadata enrichment, PII/CJIS redaction, and backpressure/batching |
| **Kernel safety net** | Grafana Beyla (eBPF) | Zero-code RED metrics + L7 traces for un-annotated / compiled (Go, Rust, C++) and COTS workloads |
| **Storage** | ClickHouse HA + ClickHouse Keeper | Columnar telemetry store; 2-node replication with Raft consensus for high availability and fast analytics |
| **Cold tiering** | MinIO (S3-compatible) | Automatic hot→cold migration of aged partitions to object storage |
| **APM UI / query** | SigNoz | Datadog-style dashboards, trace explorer, and the analytical query engine over ClickHouse |
| **Profiling** | Pyroscope | Continuous CPU/memory flame graphs (F010) |
| **Infra metrics** | node-exporter + kube-state-metrics | Host and Kubernetes object metrics (F009) |
| **Alerting / paging** | Declarative rules + Alertmanager-style dedup → ServiceNow webhook | Firing/resolved state sync, duplicate suppression, exponential-backoff retry (F011/F013) |
| **SLOs** | Custom SLO tracker service | Error-budget burn-down and multi-window burn-rate monitors (F012) |
| **Synthetics** | Canary prober (+ Playwright-style probes) | Scheduled blackbox API/transaction checks exposed as Prometheus metrics (F018) |
| **RUM** | Custom RUM collector + DOM replay player | Frontend session capture with client- and server-side PII masking (F017) |
| **Identity** | Keycloak-style OIDC IdP + SSO gateway | Agency SSO, PIV/CAC claims, group→role RBAC, multi-tenant header injection (F016) |
| **AIOps** | EWMA / seasonal decomposition; topological correlation; in-boundary (GovCloud Bedrock) LLM | Anomaly + forecast monitors, root-cause grouping, NL-to-SQL query and incident summaries (F019–F021) |
| **Runtime** | Python 3.12 stdlib `http.server` | All demo microservices are dependency-free single-file servers — easy to read, run, and air-gap |
| **Packaging / infra** | Kubernetes, Helm, Helmfile, Docker Registry v2 mirror | `helmfile sync` deploys all operators + workloads in one command; `charts/argus` holds all 89 resources |
| **Tooling** | `kubectl`, `bash`, `jq`, `curl` | Deploy and verification scripts |

---

## Getting Started

**Is it easy to set up?** Yes for a quick look, moderate for the full platform.

| Path | Needs | Time | Good for |
| :--- | :--- | :--- | :--- |
| [Single service](#option-a--run-a-single-service-locally-no-cluster) | `python3` only | ~30s | Reading code, trying an API, demos |
| [deploy.sh / deploy.ps1 (recommended)](#option-b--one-command-deploy-deploysh--deployps1) | k8s + mirror + `helmfile` | ~20–40m | Full platform, single script, cross-platform |
| [Helmfile direct](#option-c--helmfile-direct) | k8s + mirror + `helmfile` | ~20–40m | Full platform without wrapper script |
| [Manual](#option-d--manual-step-by-step-deploy-kubernetes) | k8s + mirror + `kubectl`/`jq` | ~30–50m | Granular control, partial deploys |

### Prerequisites

- **Single service:** Python 3.12+ (standard library only — no `pip install`).
- **Full platform:** Docker Desktop or Minikube with Kubernetes v1.28+; active context (`kubectl config current-context`); a local registry mirror on `localhost:5001`; `kubectl`, `jq`, `curl`, `bash` on PATH.
- **Helmfile path (additionally):** [`helmfile`](https://helmfile.readthedocs.io/en/latest/#installation) v0.169+ and `helm` v3.14+ on PATH. Install: `brew install helmfile` (macOS/Linux) or download from [GitHub releases](https://github.com/helmfile/helmfile/releases) (Windows).
- **Control-plane resource floor (Docker Desktop):** Allocate at least **8 GiB RAM**, **4+ vCPUs**, and SSD-backed virtual disk storage with **> 20% free disk capacity** (low disk IOPS or VM swap thrashing will starve `etcd` boltdb reads and `kube-apiserver`). Deploy scripts enforce `./scripts/check-control-plane-health.sh` before driving rollout load.

### Option A — Run a Single Service Locally (no cluster)

Every microservice is a dependency-free Python 3.12 stdlib server. Clone the repo and run any one directly — no Docker, no Kubernetes:

```bash
# Identity provider (issues OIDC/JWT tokens)
PORT=8089 python3 deploy/sso/idp_mock.py

# In another shell: exchange credentials for a token
curl -s -X POST localhost:8089/protocol/openid-connect/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice.admin@dhs.gov","password":"admin_pass"}'
```

```bash
# AIOps NL-to-SQL copilot
PORT=9098 python3 deploy/llm/aiops_llm_service.py
curl -s -X POST localhost:9098/api/nl-query \
  -H 'X-Argus-Test-Role: admin' -H 'Content-Type: application/json' \
  -d '{"query":"top 5 slowest endpoints by p95 latency in the last hour"}'
```

```bash
# RUM collector + DOM replay — open the demo in a browser
PORT=8082 python3 deploy/rum/rum_collector.py
#   http://localhost:8082/checkout                    (sample instrumented page)
#   http://localhost:8082/v1/rum/player/<session_id>  (replay player)
```

Most services also expose `/healthz`, `/metrics` (Prometheus), and `/api/status`.

### Option B — One-Command Deploy (deploy.sh / deploy.ps1)

`deploy.sh` (Mac/Linux) and `deploy.ps1` (Windows/PowerShell) are the recommended entry point. They run all four deploy phases in the correct order, with flags to skip phases you've already completed.

**Mac / Linux**
```bash
./deploy.sh
```

**Windows (PowerShell)**
```powershell
.\deploy.ps1
```

#### What the script does (in order)

| Phase | What runs | Can skip |
| :--- | :--- | :--- |
| 1 — Mirror | `deploy/mirror/setup-mirror.sh` — starts the local Docker registry and pulls all images into `localhost:5001` | `--skip-mirror` / `-SkipMirror` |
| 2 — Helmfile | `helmfile apply` — deploys all 3 operators then the full `argus` Helm chart | — |
| 3 — Control plane | `kubectl apply -f deploy/control-plane/etcd-maintenance.yaml` — etcd compaction CronJob (not in the Helm chart) | — |
| 4a — Tenancy | `deploy/tenancy/apply-tenancy.sh` — ClickHouse RLS policies, tenant accounts, row quotas | `--skip-tenancy` / `-SkipTenancy` |
| 4b — SLO | `deploy/slo/apply-slo.sh` — pushes declarative SLO alert rules into SigNoz Ruler | `--skip-slo` / `-SkipSlo` |

#### All flags

**Bash**
```bash
./deploy.sh [--skip-mirror] [--skip-tenancy] [--skip-slo] [--namespace <ns>]
```

**PowerShell**
```powershell
.\deploy.ps1 [-SkipMirror] [-SkipTenancy] [-SkipSlo] [-Namespace <ns>]
```

| Flag | Default | Purpose |
| :--- | :--- | :--- |
| `--skip-mirror` / `-SkipMirror` | off | Skip image mirror setup — use when the registry at `localhost:5001` is already populated (saves ~10–20 min on subsequent deploys) |
| `--skip-tenancy` / `-SkipTenancy` | off | Skip ClickHouse RLS and tenant policy apply — use when re-deploying without changing tenancy config |
| `--skip-slo` / `-SkipSlo` | off | Skip SLO alert-rule sync — use when SLO definitions haven't changed |
| `--namespace` / `-Namespace` | `argus-system` | Deploy into a different namespace (also respects `$ARGUS_NAMESPACE` env var) |

#### Common invocations

```bash
# First-ever deploy — runs everything
./deploy.sh

# Re-deploy after a code change (mirror already populated)
./deploy.sh --skip-mirror

# Re-deploy, skip all post-config (fastest helmfile-only re-apply)
./deploy.sh --skip-mirror --skip-tenancy --skip-slo

# Deploy to a custom namespace
./deploy.sh --namespace staging

# PowerShell — first deploy
.\deploy.ps1

# PowerShell — skip mirror on re-deploy
.\deploy.ps1 -SkipMirror -SkipTenancy -SkipSlo
```

> **Note (Windows):** `deploy.ps1` calls `bash` for the sub-scripts (`setup-mirror.sh`, `apply-tenancy.sh`, `apply-slo.sh`). WSL or Git Bash must be on `PATH`.

---

### Option C — Helmfile Direct

Runs only the Helm releases (phases 2 of the deploy script) without the mirror setup or post-deploy config. Useful if you manage the mirror and post-config separately.

```bash
# Add chart repos (first time only)
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo add clickhouse-operator https://docs.altinity.com/clickhouse-operator/
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helmfile apply
```

Override namespace or registry:
```bash
ARGUS_NAMESPACE=my-ns ARGUS_IMAGE_REGISTRY=my.registry:5000 helmfile apply
```

---

### Option D — Manual Step-by-Step Deploy (Kubernetes)

**1. Check readiness & initialize the air-gapped mirror**
```bash
./scripts/init.sh                 # baseline readiness audit
./deploy/mirror/setup-mirror.sh   # mirror images into localhost:5001
```

**2. Deploy the telemetry spine**
```bash
./scripts/deploy-operators.sh         # OTel, Altinity ClickHouse & Prometheus operators
./scripts/deploy-clickhouse.sh        # S3/MinIO storage + ClickHouse HA
./scripts/deploy-otel.sh              # OTel Collector DaemonSet + Gateway
./scripts/deploy-signoz.sh            # SigNoz APM UI & query engine
kubectl apply -f deploy/ebpf/beyla.yaml   # eBPF safety net
```

**3. Deploy the platform layers** (each is independent — these *are* Argus)
```bash
./deploy/alerting/apply-rules.sh          # alerting engine
./deploy/slo/apply-slo.sh                 # SLO / error budgets
./deploy/paging/apply-paging.sh           # paging → ServiceNow
./deploy/tenancy/apply-tenancy.sh         # multi-tenancy & RLS
./deploy/sso/apply-sso.sh                 # SSO / RBAC
./deploy/rum/apply-rum.sh                 # RUM & replay
./deploy/synthetics/apply-synthetics.sh   # synthetic probes
./deploy/aiops/apply-aiops.sh             # anomaly detection
./deploy/correlation/apply-correlation.sh # alert correlation
./deploy/llm/apply-llm.sh                 # NL query + summaries
```

**4. Access the UIs** (port-forward into the cluster)
```bash
kubectl -n argus-system port-forward svc/signoz 8080:8080            # SigNoz APM
kubectl -n argus-system port-forward svc/argus-sso-gateway 8088:8088 # then open /sso/login
```

At this point Argus is running but has **nothing to observe yet** — point a
workload at it (see [Sending Telemetry to Argus](#sending-telemetry-to-argus)).

---

## What Gets Installed

Every component deployed by `helmfile apply` (phase 2 of `deploy.sh`), grouped by purpose.

### Phase 1 — Operators (deployed in parallel, argus chart waits for all three)

| Component | Namespace | Purpose |
| :--- | :--- | :--- |
| **opentelemetry-operator** | `argus-system` | Kubernetes operator that watches `OpenTelemetryCollector` and `Instrumentation` CRDs. Manages the collector DaemonSet and gateway, and injects auto-instrumentation agents into annotated pods via a mutating admission webhook. |
| **altinity-clickhouse-operator** | `argus-system` | Kubernetes operator for `ClickHouseInstallation` and `ClickHouseKeeperInstallation` CRDs. Manages the HA ClickHouse cluster lifecycle, rolling upgrades, and schema migrations. |
| **prometheus-operator** (kube-prometheus-stack) | `argus-system` | Deploys Prometheus, Alertmanager, and the `PrometheusRule` / `ServiceMonitor` / `PodMonitor` CRDs. Argus uses it for infra metrics scraping and alert routing. |

### Phase 2 — Argus Chart (all workloads)

#### Telemetry Spine

| Component | Purpose |
| :--- | :--- |
| **argus-node-collector** (OTel DaemonSet) | Runs on every node. Receives OTLP traces/metrics/logs from auto-instrumented pods and forwards them to the gateway. |
| **argus-gateway-collector** (OTel Gateway) | Central collection choke-point. Enriches spans with Kubernetes metadata, redacts PII/CJIS identifiers in-memory, applies backpressure, then fans out to ClickHouse and SigNoz. |
| **argus-clickhouse** (ClickHouse HA) | 2-node replicated columnar store. Stores all traces, logs, and metrics in an append-optimized schema. Hot tier on local PV; cold tier migrates to MinIO. |
| **argus-keeper** (ClickHouse Keeper) | 3-node Raft consensus cluster that coordinates ClickHouse replication. Replaces ZooKeeper. |
| **signoz** | APM UI and query engine. Reads directly from ClickHouse. Provides trace explorer, dashboards, log viewer, and alert management. Exposed at `http://argus.local` via the Traefik ingress. |
| **argus-s3** (MinIO / SeaweedFS) | S3-compatible object storage for ClickHouse cold-tier partitions. |

#### Instrumentation & Collection

| Component | Purpose |
| :--- | :--- |
| **argus-beyla** (eBPF DaemonSet) | Attaches eBPF probes to Linux socket syscalls. Emits RED metrics and L7 traces for any workload — no code changes needed. Safety net for compiled, COTS, or un-annotated services. |
| **argus-node-collector** DaemonSet | Per-node OTLP receiver — collects from SDK-instrumented pods and forwards to the gateway. |
| **node-exporter** (DaemonSet) | Exposes host-level Prometheus metrics: CPU, memory, disk, network. |
| **kube-state-metrics** | Exposes Kubernetes object state as Prometheus metrics: pod status, deployment replicas, resource limits/requests. |
| **OTel Instrumentation CRD** | Cluster-wide auto-instrumentation config injected into Python, Java, and Node.js pods via a single annotation (`instrumentation.opentelemetry.io/inject-python: "true"`). |
| **argus-pyroscope** | Continuous CPU and memory profiling. Flame graphs accessible in SigNoz. |

#### Identity & Access

| Component | Purpose |
| :--- | :--- |
| **argus-sso-gateway** | Reverse proxy and auth enforcer. Validates JWT/OIDC tokens (PIV/CAC claims), maps agency groups to roles (Admin/Operator/Viewer), injects `X-Scope-TenantID` and `X-Forwarded-Role` headers, and proxies authenticated requests to SigNoz. Login portal at `/sso/login`. |
| **argus-idp** | Mock OIDC identity provider for dev/demo. Issues HS256 JWTs with agency group claims. Swap `IDP_URL` in the SSO gateway to point at real Okta or another OIDC provider in production. |

#### Operations

| Component | Purpose |
| :--- | :--- |
| **Prometheus alert rules** | Declarative firing-state alert rules managed as `PrometheusRule` CRDs. Includes deduplication and state-change suppression. |
| **argus-paging-gateway** | Receives Alertmanager webhooks, deduplicates, applies exponential-backoff retry, and opens/closes ServiceNow incidents. |
| **argus-servicenow-mock** | Stand-in for the ServiceNow Incident Table API. Used in dev/demo so paging tests don't hit a real ITSM system. |
| **argus-synthetic-prober** | Scheduled canary prober. Runs HTTP/API probes on a cron schedule and exposes results as Prometheus metrics for SLO burn-rate calculations. |
| **argus-rum-collector** | Receives Real User Monitoring events from browsers. Applies client- and server-side PII masking. Provides a session replay player at `/v1/rum/player/<session_id>`. |

#### Governance

| Component | Purpose |
| :--- | :--- |
| **Multi-tenancy (post-deploy)** | ClickHouse row-level security (RLS) policies, per-tenant user accounts, and query quotas applied by `deploy/tenancy/apply-tenancy.sh`. Each tenant sees only their own telemetry. |
| **SLO rules (post-deploy)** | Declarative SLO definitions (`deploy/slo/slo-rules.json`) pushed into SigNoz Ruler via `deploy/slo/apply-slo.sh`. Tracks error budgets and multi-window burn rates. |
| **etcd maintenance CronJob** | Runs every 15 minutes to compact and defragment the etcd boltdb. Prevents control-plane I/O latency from accumulating on long-running clusters. |

#### AIOps

| Component | Purpose |
| :--- | :--- |
| **argus-anomaly-detector** | EWMA and seasonal-decomposition (STL) monitors. Detects anomalies and generates forecast alerts without fixed thresholds. |
| **argus-correlation-engine** | Groups topologically related alerts by service graph proximity. Surfaces a probable root cause instead of a flood of individual firing alerts. |
| **argus-aiops-llm** | In-boundary NL-to-SQL copilot. Translates plain-language questions into ClickHouse queries and produces executive incident summaries. Backed by AWS GovCloud Bedrock. |

#### Ingress

| Component | Purpose |
| :--- | :--- |
| **argus Ingress** (Traefik) | Single entry point at `http://argus.local`. Routes all traffic to `argus-sso-gateway`, which enforces auth before proxying to SigNoz. Add `<node-ip>  argus.local` to `/etc/hosts` to resolve. |

---

## Accessing the Platform

After a successful deploy the platform is reachable at:

| URL | What you see |
| :--- | :--- |
| `http://argus.local` | Login via SSO gateway → SigNoz APM dashboards |
| `http://argus.local/sso/login` | Direct login portal (username/password → JWT) |
| `http://argus.local/sso/me` | Token introspection (shows your role and tenant) |

**Set up DNS (one-time):**
```bash
# Get your cluster node IP
kubectl get nodes -o wide

# Add to /etc/hosts (Mac/Linux)
echo "<node-ip>  argus.local" | sudo tee -a /etc/hosts

# Add to C:\Windows\System32\drivers\etc\hosts (Windows, run as Administrator)
# <node-ip>  argus.local
```

**Default dev credentials** (mock IdP only — change before any real use):

| Username | Password | Role |
| :--- | :--- | :--- |
| `alice.admin@dhs.gov` | `admin_pass` | Admin |
| `bob.operator@dhs.gov` | `operator_pass` | Operator |
| `carol.viewer@dhs.gov` | `viewer_pass` | Viewer |

> If you are not using the ingress (e.g. local port-forward), reach the SSO gateway directly:
> ```bash
> kubectl -n argus-system port-forward svc/argus-sso-gateway 8088:8088
> # open http://localhost:8088/sso/login
> ```

---

## Sending Telemetry to Argus

Argus ingests via the OTel Collector gateway. In-cluster that endpoint is:

| Protocol | Endpoint |
| :--- | :--- |
| OTLP/HTTP | `http://argus-gateway-collector.argus-system:4318` |
| OTLP/gRPC | `argus-gateway-collector.argus-system:4317` |

Anything that speaks OTLP (any language SDK, the OTel auto-instrumentation, or
another collector) can send traces/metrics/logs here. Three ways to get data in:

### 1. The bundled demo mesh (fastest)

The 10-service sample workload wired to this endpoint out of the box:

```bash
./demo/apply-services.sh          # deploy into the cluster, then:
kubectl -n argus-system port-forward deploy/argus-svc-gateway 8001:8001
curl -s localhost:8001/api/checkout           # one full fan-out trace
curl -s 'localhost:8001/api/checkout?trigger_error=payment'   # force an error for alerting/AIOps
```

Not part of the platform — see [`demo/README.md`](demo/README.md).

### 2. Your own workloads

- **Zero-code** — add the OTel auto-instrumentation annotation to a pod (see
  [Service Onboarding](#service-onboarding)); the webhook injects the agent and
  sets `OTEL_EXPORTER_OTLP_ENDPOINT` for you.
- **Manual** — set `OTEL_EXPORTER_OTLP_ENDPOINT=http://argus-gateway-collector.argus-system:4318`
  in your app and use any OTel SDK.

### 3. Azure services (testing against a real cloud)

Argus is **air-gapped by design** — the default posture blocks external egress.
Sending/collecting Azure telemetry means deliberately opening a path to Azure.
Pick based on whether you can run code in Azure:

**A. Azure workload pushes OTLP → Argus** *(preferred; same path as any app)*
For apps/AKS workloads you control. Instrument with an OTel SDK and export to a
reachable Argus endpoint:
- Expose the gateway outside the cluster (LoadBalancer/Ingress over TLS), or run
  an OTel Collector *agent* in Azure that forwards to Argus.
- Point the workload at it:
  ```bash
  OTEL_EXPORTER_OTLP_ENDPOINT=https://<argus-gateway-host>:4318
  ```
- Allow egress from the Azure side (and ingress to Argus) for that host/port only.

**B. Pull Azure PaaS metrics (no code in Azure)**
For resources you can't instrument (App Service, SQL DB, Storage, …). A ready
opt-in overlay ([`deploy/otel/azure-monitor-receiver.yaml`](deploy/otel/azure-monitor-receiver.yaml))
runs a dedicated collector that scrapes Azure Monitor via the contrib
`azure_monitor` receiver and forwards OTLP into the gateway:
```bash
# service principal needs the "Monitoring Reader" role
kubectl -n argus-system create secret generic argus-azure-sp \
  --from-literal=AZURE_CLIENT_SECRET='<sp-client-secret>'
# edit the REPLACE_* ids (subscription/tenant/client, cloud) in the file, then:
kubectl apply -f deploy/otel/azure-monitor-receiver.yaml
# restore the air-gap:
kubectl delete -f deploy/otel/azure-monitor-receiver.yaml
```
Requires egress to the Azure management API (`management.azure.com`, or
`management.usgovcloudapi.net` for gov) — the overlay is deliberately kept out
of every `deploy-*.sh` and is for **test clusters only**.

**C. Azure resource logs via Event Hub**
Route Azure diagnostic-setting logs to an Event Hub, then consume with the
contrib `azureeventhubreceiver`. Use when you need platform/activity logs rather
than metrics.

> ⚠️ Options B/C intentionally defeat the air-gap guarantee. Only enable them in
> a throwaway test cluster, never in the FedRAMP/CJIS production boundary.

---

## Services Reference

| Service | File | Default port | Purpose |
| :--- | :--- | :--- | :--- |
| Sample app | [`deploy/sample-app/app/server.py`](deploy/sample-app/app/server.py) | 8080 | Emits traces/logs/metrics + SLO dashboard (`/slo`); `/order` generates traffic |
| SSO gateway | [`deploy/sso/sso_gateway.py`](deploy/sso/sso_gateway.py) | 8088 | Token validation, RBAC, tenant header injection, login portal (`/sso/login`) |
| Identity provider | [`deploy/sso/idp_mock.py`](deploy/sso/idp_mock.py) | 8089 | OIDC discovery, JWKS, token issuance with PIV/CAC claims |
| RUM collector | [`deploy/rum/rum_collector.py`](deploy/rum/rum_collector.py) | 8082 | Session ingest (`/v1/rum/ingest`), replay player, PII masking |
| Anomaly detector | [`deploy/aiops/anomaly_detector.py`](deploy/aiops/anomaly_detector.py) | 9096 | EWMA + seasonal-decomposition anomaly/forecast monitors |
| Correlation engine | [`deploy/correlation/correlation_engine.py`](deploy/correlation/correlation_engine.py) | 9097 | Topological alert correlation → probable root cause |
| AIOps LLM | [`deploy/llm/aiops_llm_service.py`](deploy/llm/aiops_llm_service.py) | 9098 | NL-to-SQL telemetry queries + executive incident summaries |
| Paging gateway | [`deploy/paging/paging_gateway.py`](deploy/paging/paging_gateway.py) | 9099 | Alertmanager → ServiceNow incidents, dedup + retry |
| ServiceNow mock | [`deploy/paging/servicenow_mock.py`](deploy/paging/servicenow_mock.py) | 8088 | Stand-in Incident Table API for the paging path |
| Synthetic prober | [`deploy/synthetics/synthetic_prober.py`](deploy/synthetics/synthetic_prober.py) | 9115 | Scheduled canary probes exposed as Prometheus metrics |

Demo mesh (sample monitored workload, **not** part of the platform): [`demo/datadog-services.yaml`](demo/datadog-services.yaml) defines 10 interconnected services — `argus-svc-{gateway, auth, catalog, inventory, order, payment, billing, shipping, notification, recommendation}` — bundled only to generate realistic traffic. See [`demo/README.md`](demo/README.md).

---

## Service Onboarding

Two complementary strategies achieve full observability across workloads.

### Strategy A: Zero-Code Auto-Instrumentation (application layer)

For microservices on standard runtimes (Python, Java, Node.js). Agents are injected at pod creation via the OpenTelemetry mutating admission webhook. Add a single annotation:

```yaml
spec:
  template:
    metadata:
      annotations:
        instrumentation.opentelemetry.io/inject-python: "true"   # or inject-java / inject-nodejs
```

See [`docs/runbooks/service-onboarding.md`](docs/runbooks/service-onboarding.md) for end-to-end guidance.

### Strategy B: eBPF Safety Net (kernel socket layer)

For legacy services, compiled binaries (Go, Rust, C++), COTS containers, or un-annotated workloads. Grafana Beyla runs as a DaemonSet ([`deploy/ebpf/beyla.yaml`](deploy/ebpf/beyla.yaml)), attaching eBPF probes to Linux socket syscalls:

- Emits RED metrics (`http_server_request_duration_seconds`, error rates, call counts).
- Emits network-level L7 traces to `argus-gateway-collector:4318`.
- Overhead bounded to < 5% CPU per node and < 256Mi RAM.

---

## Testing & Verification

No feature is marked complete without green functional **and** edge-case suites.

```bash
./scripts/verify.sh   # full end-to-end regression suite
```

Per-feature suites live in `scripts/` as `test-<feature>.sh` (plus `-edge-cases.sh`) and `run_<feature>_e2e.py`. The spine battery covers:

| # | Suite | Target |
| :--- | :--- | :--- |
| 1 | [`check-architecture.sh`](scripts/check-architecture.sh) | Layer boundaries & namespace separation |
| 2 | [`test-edge-cases.sh`](scripts/test-edge-cases.sh) | Core platform resilience & crash recovery |
| 3–4 | `test-clickhouse-*.sh` | ClickHouse HA, S3 tiering, Keeper consensus & partition recovery |
| 5–6 | `test-otel-*.sh` | Collector DaemonSet/Gateway routing, backpressure, partitions |
| 7–8 | `test-correlation-*.sh` | 3-way TraceId join; missing context, malformed spans, clock skew |
| 9–10 | `test-redaction-*.sh` | PII/CJIS redaction incl. regex evasion & unicode bypass |
| 11–12 | `test-signoz-*.sh` | SigNoz UI/engine & cold-start resilience |
| 13–14 | `test-auto-instrumentation-*.sh` | Zero-code webhook injection & edge cases |
| 15–16 | `test-ebpf-*.sh` | eBPF discovery, RED export, zero-egress audit |
| 17 | [`init.sh`](scripts/init.sh) | Air-gap cluster readiness audit |

---

## Project Structure

```
argus/
├── deploy.sh                  # Full deploy script — Mac/Linux (recommended entry point)
├── deploy.ps1                 # Full deploy script — Windows/PowerShell
├── helmfile.yaml              # Helm release definitions (used by deploy.sh phase 2)
├── charts/
│   └── argus/                 # Helm chart — all platform workload resources
│       ├── Chart.yaml
│       ├── values.yaml        # imageRegistry, secrets, image tags, ingress config
│       ├── templates/         # 18 template files (secrets, storage, CH, SigNoz,
│       │                      #   OTel, Beyla, Pyroscope, paging, SSO, RUM,
│       │                      #   synthetics, AIOps, correlation, LLM, sample-app,
│       │                      #   alerting, demo mesh, ingress)
│       └── files/             # Symlinks → deploy/*/​*.py + demo/service_template.py
├── deploy/                    # The platform — declarative Kubernetes manifests
│   ├── aiops/                 # Anomaly & forecast detector (F019)
│   ├── alerting/              # Declarative alert rules & dedup (F011)
│   ├── clickhouse/            # ClickHouse HA, Keeper & OTel schema DDL
│   ├── correlation/           # Topological alert correlation engine (F020)
│   ├── ebpf/                  # Grafana Beyla DaemonSet, ConfigMap & RBAC
│   ├── helm/values/           # Operator Helm values (OTel, Altinity, Prometheus)
│   ├── infra-metrics/         # node-exporter + kube-state-metrics (F009)
│   ├── llm/                   # NL-query + incident-summary copilot (F021)
│   ├── mirror/                # Air-gapped registry catalog & sync scripts
│   ├── otel/                  # OTel collector DaemonSet, Gateway & CRDs
│   ├── paging/                # Paging gateway + ServiceNow mock (F013)
│   ├── profiling/             # Pyroscope continuous profiling (F010)
│   ├── rum/                   # RUM collector & DOM replay (F017)
│   ├── sample-app/            # Sample & auto-instrumented test apps
│   ├── signoz/                # SigNoz APM UI, query service & schema migration
│   ├── slo/                   # SLO tracking & error budgets (F012)
│   ├── sso/                   # SSO gateway + OIDC IdP (F016)
│   ├── storage/               # MinIO S3 cold-storage tier
│   ├── synthetics/            # Synthetic canary prober (F018)
│   └── tenancy/               # Multi-tenancy & RLS (F015)
├── demo/                      # Sample monitored workload (10-svc mesh) — NOT the platform
├── docs/                      # Technical docs & runbooks (ADRs, onboarding)
├── scripts/                   # Deploy + verification test suites
└── .harness/                  # Project tracking (specs, roadmap, dependency graph)
```

---

## Platform Details

### Ingest Security & CJIS/PII Redaction

Under FedRAMP High and CJIS mandates, every span and log record passes through the gateway transform processor before being written to disk:

1. **CJIS FBI numbers** — `\b[0-9]{7}[A-Z0-9]{2}\b` → `[REDACTED_CJIS_FBI_NUMBER]`.
2. **SSNs** — `\b\d{3}-\d{2}-\d{4}\b` → `[REDACTED_SSN]`.
3. **Payment cards (PAN)** — 13–19 digit cards → `[REDACTED_CREDIT_CARD]`.
4. **Credentials** — bearer tokens, Authorization headers, password params → `[REDACTED_CREDENTIAL]`.

Verified by [`scripts/test-redaction.sh`](scripts/test-redaction.sh) and [`scripts/test-redaction-edge-cases.sh`](scripts/test-redaction-edge-cases.sh).

### High Availability & Storage Tiering

ClickHouse HA via the Altinity ClickHouse Operator:

- **Topology** — 2-node replicated cluster (`chi-argus-clickhouse-argus-cluster-0-0-0`, `...-0-1-0`).
- **Consensus** — ClickHouse Keeper, 3-node Raft ([`deploy/clickhouse/clickhouse-keeper.yaml`](deploy/clickhouse/clickhouse-keeper.yaml)).
- **Tiering (`hot_to_cold`)** — hot tier on local PV; cold tier on MinIO ([`deploy/storage/s3-storage.yaml`](deploy/storage/s3-storage.yaml)); migration at 90% hot-volume utilization.

### Air-Gap & Mirror Management

No runtime egress to public registries or SaaS. All images/artifacts are mirrored locally:

- **Local mirror** — Docker Registry v2 at `localhost:5001`.
- **Inventory** — [`deploy/mirror/images.txt`](deploy/mirror/images.txt).
- **Sync** — [`deploy/mirror/setup-mirror.sh`](deploy/mirror/setup-mirror.sh).

Every manifest references `localhost:5001/argus/<image>:<tag>` directly.

---

## Roadmap

**21 / 21 features complete** across 5 phases, plus the bundled 10-service demo mesh.

| ID | Title | Phase | Status |
| :--- | :--- | :--- | :--- |
| F001 | Cluster baseline & air-gapped operators | 01 | ✅ |
| F002 | ClickHouse HA (2-node + S3 storage policy) | 01 | ✅ |
| F003 | OTel collector pipeline (DaemonSet + Gateway) | 01 | ✅ |
| F004 | 3-way trace + metric + log correlation | 01 | ✅ |
| F005 | Ingest PII & CJIS redaction processor | 01 | ✅ |
| F006 | SigNoz APM UI & ClickHouse analytics | 02 | ✅ |
| F007 | Zero-code auto-instrumentation & runbook | 02 | ✅ |
| F008 | eBPF safety net (Beyla service map) | 02 | ✅ |
| F009 | Infra metrics (node-exporter + KSM) | 02 | ✅ |
| F010 | Continuous profiling (Pyroscope) | 02 | ✅ |
| F011 | Alerting / monitors (firing-state + dedup) | 03 | ✅ |
| F012 | SLO tracking & error budgets | 03 | ✅ |
| F013 | Paging path (ServiceNow incident webhook) | 03 | ✅ |
| F014 | Retention, downsampling & log-level filters | 03 | ✅ |
| F015 | Multi-tenancy & cardinality guardrails | 03 | ✅ |
| F016 | SSO / RBAC via agency IdP (OIDC/PIV) | 03 | ✅ |
| F017 | RUM & DOM session replay | 04 | ✅ |
| F018 | Synthetics (Playwright probes) | 04 | ✅ |
| F019 | Anomaly & forecast monitors (EWMA/STL) | 05 | ✅ |
| F020 | Alert correlation & root-cause grouping | 05 | ✅ |
| F021 | NL query & incident-brief copilot (Bedrock) | 05 | ✅ |

The full dependency matrix and parallel-execution track topology live in [`.harness/PARALLEL_EXECUTION_GRAPH.md`](.harness/PARALLEL_EXECUTION_GRAPH.md).

---

## Troubleshooting

- **Control-plane / `etcd` disk I/O latency** — If `kubectl` times out (`TLS handshake timeout` / `context deadline exceeded`) or `etcd` logs `apply request took too long`, run `./scripts/maintain-etcd.sh` to compact old revisions and defragment the boltdb file (works via `docker exec` even when `kube-apiserver` is degraded). Periodic compaction/defrag is scheduled declaratively via [`deploy/control-plane/etcd-maintenance.yaml`](deploy/control-plane/etcd-maintenance.yaml), and [`scripts/check-control-plane-health.sh`](scripts/check-control-plane-health.sh) gates deployments on `/readyz` and `etcd` apply latency.
- **ClickHouse Keeper startup timing** — on Docker Desktop, Keeper replays uncompacted Raft changelogs at startup. The pod uses a `startupProbe` with a 300s window (`failureThreshold: 60, periodSeconds: 5`) to avoid premature liveness kills during WAL replay.
- **eBPF kernel compatibility** — Beyla needs Linux kernel 5.8+ with BPF support. Pods need `privileged: true` (or `CAP_BPF`, `CAP_PERFMON`, `CAP_NET_ADMIN`) and a `/sys/kernel/debug` mount.
- **Collector gateway ingest** — gateway listens on `4317` (gRPC) and `4318` (HTTP); workloads route to `http://argus-gateway-collector.argus-system.svc.cluster.local:4318`.

---

## Contributing

1. Branch from `main`.
2. Keep every feature backed by functional **and** edge-case suites; run `./scripts/verify.sh` before opening a PR.
3. Follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) (`feat:`, `fix:`, `docs:`, …).
4. Review and address open security findings (issue [#2](https://github.com/nimatrazmjo/argus/issues/2)) rather than extending vulnerable patterns.

---

## License

No license file is currently present in this repository; usage rights are undefined until one is added. Treat it as an internal DHS reference project unless a `LICENSE` is committed.
