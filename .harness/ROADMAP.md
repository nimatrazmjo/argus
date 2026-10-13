# ROADMAP

All features across all phases, with permanent ids, execution modes, dependency constraints, and status. This is the source of truth for **scope** and **execution order**. Statuses: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `IN REVIEW` · `COMPLETE` · `DEPRECATED`.

See [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md) for the complete dependency graph, wave definitions, conflict analysis, and subagent orchestration protocol.

**Progress**: 8 / 21 COMPLETE (38%)

> **The requirement**: a self-hosted, air-gapped Datadog-equivalent for internal DHS use, running entirely in Kubernetes. Spine = OpenTelemetry Collector -> ClickHouse -> SigNoz.  
> **Execution Model**: Phased execution with concurrent multi-track waves. Within a track, tasks execute sequentially; across tracks, tasks execute concurrently via parallel subagents. All tracks synchronize at hard Wave Gates before advancing. Full acceptance criteria for each feature live in `phases/PHASE-XX-*.md`.

---

## Phase 01 — Foundation (prove the spine, end to end, air-gapped)
*Execution Wave: Wave 1 (Spine Baseline) — Gate G1: PASSED (100% Complete)*

- [x] **F001** — Cluster baseline: operators (OTel, ClickHouse/Altinity, Prometheus) installed from a mirrored internal registry via Helm; `init.sh` + `check-architecture.sh` stood up
  - **Mode**: `[SEQUENTIAL GATE]` (Spine Baseline)
  - **Must wait for**: None (Root task)
  - **Can run in parallel with**: None
  - **Status**: `COMPLETE`

- [x] **F002** — ClickHouse HA (2 nodes + replica) with S3/MinIO-backed storage policy, healthy
  - **Mode**: `[SEQUENTIAL GATE]` (Spine Baseline)
  - **Must wait for**: F001
  - **Can run in parallel with**: None
  - **Status**: `COMPLETE`

- [x] **F003** — OTel Collector pipeline: node DaemonSet + gateway Deployment, OTLP in -> ClickHouse out, k8s resource enrichment
  - **Mode**: `[SEQUENTIAL GATE]` (Spine Baseline)
  - **Must wait for**: F002
  - **Can run in parallel with**: None
  - **Status**: `COMPLETE`

- [x] **F004** — End-to-end correlation proof: one sample app's metric + trace + log correlate by trace id in SigNoz; e2e test asserts it
  - **Mode**: `[SEQUENTIAL GATE]` (Spine Baseline)
  - **Must wait for**: F003
  - **Can run in parallel with**: None
  - **Status**: `COMPLETE`

- [x] **F005** — PII/CJIS redaction processor in the collector pipeline; sensitive fields provably never land in ClickHouse
  - **Mode**: `[SEQUENTIAL GATE]` (Spine Baseline)
  - **Must wait for**: F004
  - **Can run in parallel with**: None
  - **Status**: `COMPLETE`

---

## Phase 02 — Coverage (see everything; onboarding is one line)
*Execution Waves: Wave 1 (Complete) & Wave 2 (Active)*

- [x] **F006** — SigNoz deployed, reading ClickHouse: APM, logs, traces, dashboards
  - **Mode**: `[SEQUENTIAL GATE]` (Wave 1 UI Foundation)
  - **Must wait for**: F005
  - **Can run in parallel with**: None
  - **Status**: `COMPLETE`

- [x] **F007** — Zero-code auto-instrumentation via OTel Operator annotation; onboarding runbook for app teams
  - **Mode**: `[PARALLEL TRACK A]` (Signal Expansion)
  - **Must wait for**: F006
  - **Can run in parallel with**: F008
  - **Status**: `COMPLETE`

- [x] **F008** — eBPF safety net (Beyla): network-level service map for un-annotated services
  - **Mode**: `[PARALLEL TRACK A]` (Signal Expansion)
  - **Must wait for**: F006
  - **Can run in parallel with**: F007
  - **Status**: `COMPLETE`

- [ ] **F009** — Infra metrics: node-exporter + kube-state-metrics into the store
  - **Mode**: `[PARALLEL TRACK A]` (Signal Expansion — Wave 2 Active)
  - **Must wait for**: F006, F008 (Gate G1)
  - **Can run in parallel with**: F010, F011, F014
  - **Status**: `NOT STARTED`

- [ ] **F010** — Continuous profiling (Pyroscope)
  - **Mode**: `[PARALLEL TRACK A]` (Signal Expansion — Wave 2 Active)
  - **Must wait for**: F006 (Gate G1)
  - **Can run in parallel with**: F009, F011, F014
  - **Status**: `NOT STARTED`

---

## Phase 03 — Operational layer (alerting, cost, tenancy, auth)
*Execution Waves: Wave 2 (Active), Wave 3, Wave 4*

- [ ] **F011** — Alerting/monitors: firing-state + dedup; threshold rules
  - **Mode**: `[PARALLEL TRACK B]` (Incident Lifecycle — Wave 2 Active)
  - **Must wait for**: F006 (Gate G1)
  - **Can run in parallel with**: F009, F010, F014
  - **Status**: `NOT STARTED`

- [ ] **F012** — SLO tracking + error budgets
  - **Mode**: `[PARALLEL TRACK B]` (Incident Lifecycle — Wave 3)
  - **Must wait for**: F011 (Requires alert evaluation engine)
  - **Can run in parallel with**: F013, F015, F017, F018
  - **Status**: `NOT STARTED`

- [ ] **F013** — Paging path: webhook to agency incident tooling (ServiceNow); optional Keep correlation front
  - **Mode**: `[PARALLEL TRACK B]` (Incident Lifecycle — Wave 3)
  - **Must wait for**: F011 (Requires firing alert events)
  - **Can run in parallel with**: F012, F015, F017, F018
  - **Status**: `NOT STARTED`

- [ ] **F014** — Retention + downsampling: tiered hot/cold (local -> S3), metric rollups via materialized views, default log-level filter
  - **Mode**: `[PARALLEL TRACK C]` (Data Governance & Storage — Wave 2 Active)
  - **Must wait for**: F002, F006 (Gate G1)
  - **Can run in parallel with**: F009, F010, F011
  - **Status**: `NOT STARTED`

- [ ] **F015** — Multi-tenancy + per-tenant quotas; cardinality guardrails at ingest
  - **Mode**: `[PARALLEL TRACK C]` (Data Governance & Storage — Wave 3)
  - **Must wait for**: F014 (Builds on storage policies and downsampling partitions)
  - **Can run in parallel with**: F012, F013, F017, F018
  - **Status**: `NOT STARTED`

- [ ] **F016** — SSO/RBAC via agency IdP (SAML/OIDC, PIV/CAC), role separation
  - **Mode**: `[PARALLEL TRACK C]` (Data Governance & Security — Wave 4)
  - **Must wait for**: F015 (Requires multi-tenant role/namespace isolation boundaries)
  - **Can run in parallel with**: F019, F020
  - **Status**: `NOT STARTED`

---

## Phase 04 — Frontend signals (the build-heavy, no-OSS-equal part)
*Execution Wave: Wave 3*

- [ ] **F017** — RUM + session replay (OpenReplay or HyperDX)
  - **Mode**: `[PARALLEL TRACK D]` (Frontend Signals — Wave 3)
  - **Must wait for**: F005, F006 (Gate G1; inherits PII redaction rules)
  - **Can run in parallel with**: F012, F013, F015, F018
  - **Status**: `NOT STARTED`

- [ ] **F018** — Synthetics: scheduled Playwright CronJobs + blackbox probes + results view
  - **Mode**: `[PARALLEL TRACK D]` (Frontend Signals — Wave 3)
  - **Must wait for**: F011 (Requires alerting engine to route probe breach notifications)
  - **Can run in parallel with**: F012, F013, F015, F017
  - **Status**: `NOT STARTED`

---

## Phase 05 — AIOps / the moat (deferred, optional)
*Execution Waves: Wave 4 & Wave 5 (Final Moat)*

- [ ] **F019** — Anomaly + forecast monitors (seasonal decomposition / EWMA)
  - **Mode**: `[PARALLEL TRACK E]` (AIOps & Intelligence — Wave 4)
  - **Must wait for**: F009 (Infra metric streams), F011 (Alerting framework)
  - **Can run in parallel with**: F016, F020
  - **Status**: `NOT STARTED`

- [ ] **F020** — Alert correlation + root-cause grouping
  - **Mode**: `[PARALLEL TRACK E]` (AIOps & Intelligence — Wave 4)
  - **Must wait for**: F011 (Alert events), F013 (Incident records), F019 (Anomaly alerts)
  - **Can run in parallel with**: F016
  - **Status**: `NOT STARTED`

- [ ] **F021** — NL query + incident summarization (LLM layer; Bedrock-backed)
  - **Mode**: `[SEQUENTIAL GATE]` (Wave 5 Final Platform Moat)
  - **Must wait for**: F014 (Data schemas/rollups), F016 (RBAC boundaries), F019, F020 (Incident correlation graphs)
  - **Can run in parallel with**: None (Final sequential integration gate before full ATO sign-off)
  - **Status**: `NOT STARTED`
