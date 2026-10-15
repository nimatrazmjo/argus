# CURRENT TASK — PARALLEL DISPATCH CONTROL

**Wave**: **Wave 3 — Operational Depth & Frontend Signals**  
**Execution Mode**: Parallel Multi-Subagent Dispatch (see [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md))  
**Gate Status**: Gate G1 is **PASSED** (8/21 Complete — 38%). Gate G2 is **PASSED** (12/21 Complete — 57%).  
**Active Wave Features**: `F012` (Track B) || `F013` (Track B) || `F015` (Track C) || `F017` (Track D) || `F018` (Track D)

---

## Completed in Wave 2 (All Packages Verified 100% Green)

### Package 1: Track A — Feature F009 (Infra Metrics) — [COMPLETE]
- **Status**: COMPLETE & VERIFIED. Evidence saved to `.harness/evidence/F009/`.
- **Delivered**: `deploy/infra-metrics/node-exporter.yaml`, `deploy/infra-metrics/kube-state-metrics.yaml`, OTel gateway & node scraper pipelines.

### Package 2: Track A — Feature F010 (Continuous Profiling) — [COMPLETE]
- **Status**: COMPLETE & VERIFIED. Evidence saved to `.harness/evidence/F010/`.
- **Delivered**: `deploy/profiling/pyroscope.yaml`, `docs/decisions/ADR-0006-continuous-profiling-pyroscope.md`, `scripts/test-profiling.sh`, `scripts/test-profiling-edge-cases.sh`.

### Package 3: Track B — Feature F011 (Alerting / Monitors Core) — [COMPLETE]
- **Status**: COMPLETE & VERIFIED. Evidence saved to `.harness/evidence/F011/`.
- **Delivered**: `deploy/alerting/rules.json`, `deploy/alerting/apply-rules.sh`, `deploy/alerting/prometheus-rules.yaml`, `docs/decisions/ADR-0007-alerting-and-monitors-signoz.md`, `scripts/test-alerting.sh`, `scripts/test-alerting-edge-cases.sh`.

### Package 4: Track C — Feature F014 (Retention & Downsampling) — [COMPLETE]
- **Status**: COMPLETE & VERIFIED. Evidence saved to `.harness/evidence/F014/`.
- **Delivered**: `deploy/clickhouse/retention-policies.sql`, `scripts/test-retention-downsampling.sh`, `scripts/test-retention-edge-cases.sh`.

---

## Active Wave 3 Parallel Work Packages

The orchestrator dispatches parallel subagents across the independent tracks in Wave 3:

### Package 1: Track B — Feature F012 (SLO Tracking & Error Budgets)
- **Scope**: Implement Service Level Objectives (SLO), burn-rate alerts, and error budgets against APM and infrastructure metrics.
- **Target Files**: `deploy/slo/`, `scripts/test-slo.sh`, `scripts/test-slo-edge-cases.sh`.
- **Prerequisites**: F011 (Gate G2 PASSED).

### Package 2: Track B — Feature F013 (Paging Webhook & Incident Routing)
- **Scope**: Implement incident paging webhooks to external/internal incident response tools (ServiceNow-compatible payload formats, optional Keep correlation interface).
- **Target Files**: `deploy/paging/`, `scripts/test-paging.sh`, `scripts/test-paging-edge-cases.sh`.
- **Prerequisites**: F011 (Gate G2 PASSED).

### Package 3: Track C — Feature F015 (Multi-Tenancy, Quotas & Cardinality Guardrails)
- **Scope**: Configure tenant isolation, per-tenant resource limits/quotas, and gateway ingestion cardinality guardrails.
- **Target Files**: `deploy/tenancy/`, `deploy/otel/processors/cardinality-processor.yaml`, `scripts/test-tenancy.sh`.
- **Prerequisites**: F014 (Gate G2 PASSED).

### Package 4: Track D — Feature F017 (Real User Monitoring / Session Replay)
- **Scope**: Deploy RUM / session replay engine (OpenReplay/HyperDX) with PII redaction and frontend telemetry ingestion.
- **Target Files**: `deploy/rum/`, `scripts/test-rum.sh`, `scripts/test-rum-edge-cases.sh`.
- **Prerequisites**: F005, F006 (Gate G1 PASSED).

### Package 5: Track D — Feature F018 (Synthetic Canary Probing via Playwright)
- **Scope**: Scheduled Playwright CronJobs executing blackbox synthetic health probes with alerting integration on probe failure.
- **Target Files**: `deploy/synthetics/`, `scripts/test-synthetics.sh`, `scripts/test-synthetics-edge-cases.sh`.
- **Prerequisites**: F011 (Gate G2 PASSED).

---

## Next Immediate Step
Launch Wave 3 parallel subagents via `invoke_subagent` for Track B (F012 SLOs / F013 Paging), Track C (F015 Multi-Tenancy), and Track D (F017 RUM / F018 Synthetics).
