# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Execution Architecture**: Multi-Track Concurrent Execution Model (see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md))
- **Active Wave**: **Wave 2 — Concurrent Coverage & Operations Foundation**
- **Active Features (Ready for Parallel Dispatch)**:
  - **Track A**: `F010` — Continuous profiling (`Pyroscope`)
  - **Track B**: `F011` — Alerting / monitors (firing-state + dedup, threshold rules)
  - **Track C**: `F014` — Retention + downsampling (hot/cold tiering, materialized views rollups, log filter)
- **Overall progress**: 9 / 21 features COMPLETE (43%)
- **Milestone status**:
  - **Wave 1 (Foundation & Core Coverage)**: 100% COMPLETE (F001 through F008 all complete and verified).
  - **Sync Gate G1**: **PASSED**. Air-gap compliant core spine operational (OTel -> ClickHouse HA -> SigNoz + Auto-Instrumentation + eBPF Beyla).
  - **F009 (Infra Metrics)**: 100% COMPLETE (node-exporter + kube-state-metrics into ClickHouse & SigNoz).
  - **Wave 2**: Active — Dispatched across Track A (F010), Track B (F011), Track C (F014).

## Last verified
- **Date**: 2026-10-14
- **Gate G1 Status**: PASS — Baseline air-gapped spine and coverage core fully operational.
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, CRDs present, Altinity ClickHouse HA Ready, Keeper Ready, OTel Gateway & Node DaemonSet Ready, Beyla eBPF DaemonSet Ready, node-exporter Ready, kube-state-metrics Ready, SigNoz UI & Query Ready, 100% mirrored image origins `localhost:5001/argus/*`).
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (19-step verification suite including baseline, edge cases, ClickHouse storage tiering, OTel pipelines, trace/metric/log correlation, CJIS/PII redaction, SigNoz APM, auto-instrumentation, Beyla eBPF network maps, node-exporter & kube-state-metrics infra metrics).
- **Evidence**: Captured under `.harness/evidence/` (F001 through F009).

## Parallel Execution Strategy (Wave 2)
The orchestrator dispatches independent subagents across three non-interfering tracks:
1. **Track A (Subagents 1 & 2)**: Expand signal collection with host/cluster infrastructure metrics (F009) and continuous CPU/memory profiling (F010).
2. **Track B (Subagent 3)**: Stand up the alert evaluation, threshold monitoring, and deduplication engine (F011).
3. **Track C (Subagent 4)**: Implement storage retention TTLs, S3 cold storage policies, metric rollup materialized views, and collector log-level filtering (F014).

All four features execute concurrently without port collisions, CRD contention, or database locks. Upon completion, the orchestrator verifies **Gate G2** before unlocking Wave 3.

## Open blockers
See `BLOCKERS.md`. None. Cluster, internal registry mirror, ClickHouse HA, and SigNoz are fully operational.

## Notes for agents
- Archetype is **DevOps/IaC (archetype B)**.
- Strict air-gap enforcement: 100% of container images must resolve from `localhost:5001/argus/*`.
- Multi-agent orchestration protocol defined in `.harness/PARALLEL_EXECUTION_GRAPH.md`.
- Concurrency rules: features within the active wave on separate tracks run in parallel; features with dependencies wait at synchronization gates.
- Every completed feature must fulfill its definition of done: phase criteria met, test scripts added to `scripts/verify.sh`, edge cases verified, evidence captured under `.harness/evidence/<FID>/`.
