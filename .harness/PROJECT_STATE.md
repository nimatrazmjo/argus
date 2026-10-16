# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Execution Architecture**: Multi-Track Concurrent Execution Model (see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md))
- **Active Wave**: **Wave 4 — Security, Compliance & Cost Governance** (Unlocked at Gate G3)
- **Gate Status**:
  - **Sync Gate G1**: **PASSED**. Air-gap compliant core spine operational (OTel -> ClickHouse HA -> SigNoz + Auto-Instrumentation + eBPF Beyla).
  - **Sync Gate G2**: **PASSED**. Concurrent Coverage & Operations Foundation 100% complete across all 4 parallel tracks.
  - **Sync Gate G3**: **PASSED**. Operational Depth & Frontend Signals 100% complete across Tracks B, C, and D.
- **Completed in Wave 3**:
  - `F012` — SLO tracking, error budget burndown, and multi-window burn rate monitors (Complete)
  - `F013` — Paging path: ServiceNow webhook gateway, retry queue, and deduplication (Complete)
  - `F015` — Multi-tenancy: ClickHouse RLS row policies, per-tenant quotas, cardinality guardrails (Complete)
  - `F017` — Real User Monitoring (RUM) & DOM session replay beside SigNoz with multi-tier PII masking (Complete)
  - `F018` — Synthetic canary probing: multi-step blackbox checks, Prometheus :9115 exporter, failure alerts (Complete)
- **Completed in Wave 2**:
  - `F009` — Infra metrics: node-exporter + kube-state-metrics (Complete)
  - `F010` — Continuous profiling via Pyroscope (Complete)
  - `F011` — Alerting / monitors: firing-state + dedup; threshold rules (Complete)
  - `F014` — Retention & downsampling, tiered storage hot/cold, materialized views (Complete)
- **Overall progress**: 17 / 21 features COMPLETE (81%)
- **Active Features (Wave 4 & Wave 5)**:
  - **Track C**: `F016` (SSO / RBAC — Keycloak OIDC integration & role-based access control)
  - **Track E**: `F019` (Anomaly & forecast monitors — seasonal decomposition / EWMA)
  - **Track B**: `F020` (Root-cause grouping & alert topology correlation)
  - **Track E**: `F021` (Telemetry cost attribution & FinOps dashboard)

## Last verified
- **Date**: 2026-10-15
- **Full Verification Suite**: PASS — 35 / 35 verification steps passed 100% green (`scripts/verify.sh </dev/null`).
- **F017 Status**: PASS — Real User Monitoring (RUM) collector, OpenReplay-compatible rrweb DOM session recording and playback, defense-in-depth PII masking (passwords, emails, PANs, tokens), ClickHouse session persistence, and W3C traceparent APM correlation verified (`scripts/test-rum.sh` and `scripts/test-rum-edge-cases.sh`). Evidence in `.harness/evidence/F017/`.
- **F018 Status**: PASS — Synthetic Canary Prober daemon with multi-step workflows (`order_api`, `slo_dashboard`, `auth_validation`), Prometheus `:9115/metrics` exposition, target failure simulation and automatic recovery verified (`scripts/test-synthetics.sh` and `scripts/test-synthetics-edge-cases.sh`). Evidence in `.harness/evidence/F018/`.
- **F013 Status**: PASS — ServiceNow Mock API, incident translation, deduplication, retry queue with exponential backoff on destination outage, and Prometheus metrics verified (`scripts/test-paging.sh` and `scripts/test-paging-edge-cases.sh`). Evidence in `.harness/evidence/F013/`.
- **F015 Status**: PASS — ClickHouse Row-Level Security (`ResourceAttributes['tenant_id'] = currentUser()`), strict per-tenant row-read quotas, and OTel collector cardinality guardrail processor verified (`scripts/test-tenancy.sh` and `scripts/test-tenancy-edge-cases.sh`). Evidence in `.harness/evidence/F015/`.
- **F012 Status**: PASS — OpenSLO specification, SigNoz Ruler multi-window burn rate alerts, error budget burndown, visual dashboard, and 6 edge case scenarios verified (`scripts/test-slo.sh` and `scripts/test-slo-edge-cases.sh`). Evidence saved to `.harness/evidence/F012/`.
- **Gate G2 Status**: PASS — Wave 2 features (F009, F010, F011, F014) fully verified and regression-free.
- **F011 Status**: PASS — Centralized threshold evaluation, Alertmanager deduplication, flapping hysteresis, and deadman absence monitoring verified (`scripts/test-alerting.sh` and `scripts/test-alerting-edge-cases.sh`). Evidence saved to `.harness/evidence/F011/`.
- **F010 Status**: PASS — Continuous profiling via Pyroscope verified with live CPU and memory flame graphs (`scripts/test-profiling.sh` and `scripts/test-profiling-edge-cases.sh`). Evidence saved to `.harness/evidence/F010/`.
- **F014 Status**: PASS — Tiered storage (hot SSD -> cold S3), downsampling materialized views (raw -> 1m -> 1h), and OTel log filtering verified (`scripts/test-retention-downsampling.sh` and `scripts/test-retention-edge-cases.sh`). Evidence saved to `.harness/evidence/F014/`.

## Parallel Execution Strategy (Wave 4)
The orchestrator dispatches independent subagents across the Wave 4 tracks:
1. **Track C (Security & Identity)**: Feature F016 (SSO / RBAC via Keycloak OIDC).
2. **Track E (Intelligence & AIOps)**: Feature F019 (Anomaly detection and forecast monitors) & Feature F021 (Cost attribution).
3. **Track B (Incident Correlation)**: Feature F020 (Root-cause grouping & alert topology correlation).

## Open blockers
See `BLOCKERS.md`. None. Cluster, internal registry mirror, ClickHouse HA, SigNoz APM, Pyroscope profiling, Alerting engine, Paging Gateway, and RUM Replay Engine are fully operational.

## Notes for agents
- Archetype is **DevOps/IaC (archetype B)**.
- Strict air-gap enforcement: 100% of container images must resolve from `localhost:5001/argus/*`.
- Multi-agent orchestration protocol defined in `.harness/PARALLEL_EXECUTION_GRAPH.md`.
- Concurrency rules: features within the active wave on separate tracks run in parallel; features with dependencies wait at synchronization gates.
- Every completed feature must fulfill its definition of done: phase criteria met, test scripts added to `scripts/verify.sh`, edge cases verified, evidence captured under `.harness/evidence/<FID>/`.
