# CURRENT TASK — PARALLEL DISPATCH CONTROL

**Wave**: **Wave 2 — Concurrent Coverage & Operations Foundation**  
**Execution Mode**: Parallel Multi-Subagent Dispatch (see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md))  
**Gate Status**: Gate G1 is **PASSED** (9/21 Features Complete — 43%).  
**Active Wave Features**: `F009` (COMPLETE) | `F010` (Track A) || `F011` (Track B) || `F014` (Track C)

---

## Active Parallel Work Packages

The parent agent dispatches parallel subagents across the independent tracks in Wave 2:

### Package 1: Track A — Feature F009 (Infra Metrics) — [COMPLETE]
- **Status**: COMPLETE & VERIFIED (100% green across `scripts/test-infra-metrics.sh` and `scripts/test-infra-metrics-edge-cases.sh`). Evidence saved to `.harness/evidence/F009/`.
- **Delivered**: `deploy/infra-metrics/node-exporter.yaml`, `deploy/infra-metrics/kube-state-metrics.yaml`, OTel gateway & node scraper pipelines, 596k+ node metrics & 1.37M+ KSM metrics ingested into ClickHouse and SigNoz.

### Package 2: Track A — Feature F010 (Continuous Profiling)
- **Scope**: Deploy Pyroscope server (port 4040) and profiling agent; mirror images to internal registry; configure sample app profiling integration; verify CPU/memory flame graphs in UI.
- **Target Files**: `deploy/profiling/pyroscope.yaml`, `docs/decisions/ADR-0006-continuous-profiling.md`, `scripts/test-profiling.sh`, `scripts/test-profiling-edge-cases.sh`.
- **Concurrency**: Can run in parallel with F009, F011, and F014. Zero collision.

### Package 3: Track B — Feature F011 (Alerting / Monitors Core)
- **Scope**: Stand up threshold alerting engine with firing-state management and deduplication in SigNoz / Alertmanager; define declarative monitor CRDs/specs; verify alert fire and resolution lifecycle on induced threshold breach.
- **Target Files**: `deploy/alerting/`, `scripts/test-alerting.sh`, `scripts/test-alerting-edge-cases.sh`.
- **Concurrency**: Can run in parallel with F009, F010, and F014.

### Package 4: Track C — Feature F014 (Retention & Downsampling)
- **Scope**: Configure ClickHouse storage TTL policies (hot local NVMe -> cold MinIO S3); implement metric downsampling via materialized views (`signoz_metrics_1m`, `signoz_metrics_1h`); configure OTel gateway default log-level filter.
- **Target Files**: `deploy/clickhouse/retention-policies.sql`, `deploy/otel/processors/filter-processor.yaml`, `scripts/test-retention-downsampling.sh`.
- **Concurrency**: Can run in parallel with F009, F010, and F011.

---

## Synchronization Barrier: Gate G2
Once all active subagents complete their packages:
1. Orchestrator aggregates test scripts into `scripts/verify.sh`.
2. Runs `./scripts/verify.sh` to ensure zero regressions across all 12 completed features (F001 through F011 + F014).
3. Verifies edge case evidence in `.harness/evidence/` for F009, F010, F011, and F014.
4. Marks Gate G2 as **PASSED** in `.harness/PROJECT_STATE.md` and `.harness/ROADMAP.md`.
5. Unlocks Wave 3 parallel dispatch (`F012` || `F013` || `F015` || `F017` || `F018`).

## Next Immediate Step
Launch Wave 2 parallel subagents via `invoke_subagent` for F010 (Continuous Profiling), F011 (Alerting), and F014 (Retention & Downsampling).
