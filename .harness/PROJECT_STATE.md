# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Execution Architecture**: Multi-Track Concurrent Execution Model (see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md))
- **Active Wave**: **Wave 3 — Operational Depth & Frontend Signals** (Unlocked at Gate G2)
- **Gate Status**:
  - **Sync Gate G1**: **PASSED**. Air-gap compliant core spine operational (OTel -> ClickHouse HA -> SigNoz + Auto-Instrumentation + eBPF Beyla).
  - **Sync Gate G2**: **PASSED**. Concurrent Coverage & Operations Foundation 100% complete across all 4 parallel tracks.
- **Completed in Wave 2**:
  - `F009` — Infra metrics: node-exporter + kube-state-metrics (Complete)
  - `F010` — Continuous profiling via Pyroscope (Complete)
  - `F011` — Alerting / monitors: firing-state + dedup; threshold rules (Complete)
  - `F014` — Retention & downsampling, tiered storage hot/cold, materialized views (Complete)
- **Overall progress**: 12 / 21 features COMPLETE (57%)
- **Active Features (Ready for Wave 3 Parallel Dispatch)**:
  - **Track B**: `F012` (SLO tracking + error budgets), `F013` (Paging path / ServiceNow webhook)
  - **Track C**: `F015` (Multi-tenancy + per-tenant quotas; cardinality guardrails)
  - **Track D**: `F017` (RUM + session replay), `F018` (Synthetics: scheduled Playwright probes)

## Last verified
- **Date**: 2026-10-15
- **Gate G2 Status**: PASS — Wave 2 features (F009, F010, F011, F014) fully verified and regression-free.
- **F011 Status**: PASS — Centralized threshold evaluation, Alertmanager deduplication, flapping hysteresis, and deadman absence monitoring verified (`scripts/test-alerting.sh` and `scripts/test-alerting-edge-cases.sh`). Evidence saved to `.harness/evidence/F011/`.
- **F010 Status**: PASS — Continuous profiling via Pyroscope verified with live CPU and memory flame graphs (`scripts/test-profiling.sh` and `scripts/test-profiling-edge-cases.sh`). Evidence saved to `.harness/evidence/F010/`.
- **F014 Status**: PASS — Tiered storage (hot SSD -> cold S3), downsampling materialized views (raw -> 1m -> 1h), and OTel log filtering verified (`scripts/test-retention-downsampling.sh` and `scripts/test-retention-edge-cases.sh`). Evidence saved to `.harness/evidence/F014/`.

## Parallel Execution Strategy (Wave 3)
The orchestrator dispatches independent subagents across the Wave 3 tracks:
1. **Track B (Incident Lifecycle)**: Implement Service Level Objectives (SLO), burn-rate alerts, and error budgets (F012) and incident paging webhooks (F013).
2. **Track C (Data Governance & Security)**: Enforce tenant isolation, per-tenant resource quotas, and ingestion cardinality guardrails (F015).
3. **Track D (Frontend Signals)**: Stand up Real User Monitoring (RUM) / session replay (F017) and synthetic Playwright canary probes (F018).

All five features execute concurrently without collision.

## Open blockers
See `BLOCKERS.md`. None. Cluster, internal registry mirror, ClickHouse HA, SigNoz APM, Pyroscope profiling, and Alerting engine are fully operational.

## Notes for agents
- Archetype is **DevOps/IaC (archetype B)**.
- Strict air-gap enforcement: 100% of container images must resolve from `localhost:5001/argus/*`.
- Multi-agent orchestration protocol defined in `.harness/PARALLEL_EXECUTION_GRAPH.md`.
- Concurrency rules: features within the active wave on separate tracks run in parallel; features with dependencies wait at synchronization gates.
- Every completed feature must fulfill its definition of done: phase criteria met, test scripts added to `scripts/verify.sh`, edge cases verified, evidence captured under `.harness/evidence/<FID>/`.
