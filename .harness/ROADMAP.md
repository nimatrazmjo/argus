# ROADMAP

All features across all phases, with permanent ids and status. This is the source of truth
for **scope**. Statuses: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `IN REVIEW` ·
`COMPLETE` · `DEPRECATED`.

**Progress**: 1 / 21 COMPLETE (5%)

> The requirement: a self-hosted, air-gapped Datadog-equivalent for internal DHS use, running
> entirely in Kubernetes. Spine = OpenTelemetry Collector -> ClickHouse -> SigNoz. Phases are
> gated in order; exactly one feature is `IN PROGRESS` at a time. Full acceptance criteria for
> each feature live in its `phases/PHASE-XX-*.md`.

## Phase 01 — Foundation (prove the spine, end to end, air-gapped)
- [x] **F001** — Cluster baseline: operators (OTel, ClickHouse/Altinity, Prometheus) installed from a mirrored internal registry via Helm; `init.sh` + `check-architecture.sh` stood up — `COMPLETE`
- [ ] **F002** — ClickHouse HA (2 nodes + replica) with S3/MinIO-backed storage policy, healthy — `IN PROGRESS`
- [ ] **F003** — OTel Collector pipeline: node DaemonSet + gateway Deployment, OTLP in -> ClickHouse out, k8s resource enrichment — `NOT STARTED`
- [ ] **F004** — End-to-end correlation proof: one sample app's metric + trace + log correlate by trace id in SigNoz; e2e test asserts it — `NOT STARTED`
- [ ] **F005** — PII/CJIS redaction processor in the collector pipeline; sensitive fields provably never land in ClickHouse — `NOT STARTED`

## Phase 02 — Coverage (see everything; onboarding is one line)
- [ ] **F006** — SigNoz deployed, reading ClickHouse: APM, logs, traces, dashboards — `NOT STARTED`
- [ ] **F007** — Zero-code auto-instrumentation via OTel Operator annotation; onboarding runbook for app teams — `NOT STARTED`
- [ ] **F008** — eBPF safety net (Beyla or Pixie): network-level service map for un-annotated services — `NOT STARTED`
- [ ] **F009** — Infra metrics: node-exporter + kube-state-metrics into the store — `NOT STARTED`
- [ ] **F010** — Continuous profiling (Pyroscope) — `NOT STARTED`

## Phase 03 — Operational layer (alerting, cost, tenancy, auth)
- [ ] **F011** — Alerting/monitors: firing-state + dedup; threshold rules — `NOT STARTED`
- [ ] **F012** — SLO tracking + error budgets — `NOT STARTED`
- [ ] **F013** — Paging path: webhook to agency incident tooling (ServiceNow); optional Keep correlation front — `NOT STARTED`
- [ ] **F014** — Retention + downsampling: tiered hot/cold (local -> S3), metric rollups via materialized views, default log-level filter — `NOT STARTED`
- [ ] **F015** — Multi-tenancy + per-tenant quotas; cardinality guardrails at ingest — `NOT STARTED`
- [ ] **F016** — SSO/RBAC via agency IdP (SAML/OIDC, PIV/CAC), role separation — `NOT STARTED`

## Phase 04 — Frontend signals (the build-heavy, no-OSS-equal part)
- [ ] **F017** — RUM + session replay (OpenReplay or HyperDX) — `NOT STARTED`
- [ ] **F018** — Synthetics: scheduled Playwright CronJobs + blackbox probes + results view — `NOT STARTED`

## Phase 05 — AIOps / the moat (deferred, optional)
- [ ] **F019** — Anomaly + forecast monitors (seasonal decomposition / EWMA) — `NOT STARTED`
- [ ] **F020** — Alert correlation + root-cause grouping — `NOT STARTED`
- [ ] **F021** — NL query + incident summarization (LLM layer; Bedrock-backed) — `NOT STARTED`
