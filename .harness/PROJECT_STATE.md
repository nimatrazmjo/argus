# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Execution Architecture**: Multi-Track Concurrent Execution Model (see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md))
- **Active Wave**: **Wave 2 — Concurrent Coverage & Operations Foundation**
- **Active Features (Ready for Parallel Dispatch)**:
  - **Track B**: `F011` — Alerting / monitors (firing-state + dedup, threshold rules)
- **Completed in Wave 2**:
  - `F009` — Infra metrics: node-exporter + kube-state-metrics (Complete)
  - `F010` — Continuous profiling via Pyroscope (Complete)
  - `F014` — Retention & downsampling, tiered storage hot/cold, materialized views (Complete)
- **Overall progress**: 11 / 21 features COMPLETE (52%)
- **Milestone status**:
  - **Wave 1 (Foundation & Core Coverage)**: 100% COMPLETE (F001 through F008 all complete and verified).
  - **Sync Gate G1**: **PASSED**. Air-gap compliant core spine operational (OTel -> ClickHouse HA -> SigNoz + Auto-Instrumentation + eBPF Beyla).
  - **Wave 2**: In Final Verification — Only F011 remains before Wave Gate G2 (12 / 21 features = 57%).

## Last verified
- **Date**: 2026-10-15
- **Gate G1 Status**: PASS — Baseline air-gapped spine and coverage core fully operational.
- **F010 Status**: PASS — Continuous profiling via Pyroscope verified with live CPU and memory flame graphs (`scripts/test-profiling.sh` and `scripts/test-profiling-edge-cases.sh`). Evidence saved to `.harness/evidence/F010/`.
- **F014 Status**: PASS — Tiered storage (hot SSD -> cold S3), downsampling materialized views (raw -> 1m -> 1h), and OTel log filtering verified 100% green (`scripts/test-retention-downsampling.sh` and `scripts/test-retention-edge-cases.sh`). Evidence saved to `.harness/evidence/F014/`.

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
