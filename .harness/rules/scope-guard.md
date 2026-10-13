# Scope Guard

What is **off-limits right now**. Scope creep is the most common agent failure; this file is
the leash. The active execution wave is whatever `PROJECT_STATE.md` says. Building ahead of the
active wave or without prerequisite gate sign-off is a defect, not initiative.
Execution architecture is governed by [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md).

## Current Status: Wave 1 COMPLETE (Gate G1 PASSED) | Wave 2 ACTIVE

### Completed & Frozen (Wave 1: F001 - F008)
- F001 — operators installed from a mirrored internal registry; `init.sh` + `check-architecture.sh`. (`COMPLETE`)
- F002 — ClickHouse HA with S3/MinIO-backed storage policy. (`COMPLETE`)
- F003 — OTel Collector pipeline (node DaemonSet + gateway), OTLP -> ClickHouse, k8s enrichment. (`COMPLETE`)
- F004 — end-to-end metric+trace+log correlation by trace id, with an e2e test. (`COMPLETE`)
- F005 — PII/CJIS redaction at ingest, provable. (`COMPLETE`)
- F006 — SigNoz UI over ClickHouse. (`COMPLETE`)
- F007 — Zero-code auto-instrumentation via OTel Operator. (`COMPLETE`)
- F008 — eBPF safety net (Beyla). (`COMPLETE`)

### In Scope for Active Wave (Wave 2 — Parallel Tracks)
- **Track A**: F009 — Infra metrics (`node-exporter` + `kube-state-metrics`).
- **Track A**: F010 — Continuous profiling (`Pyroscope`).
- **Track B**: F011 — Alerting / monitors core (firing-state, dedup, threshold rules).
- **Track C**: F014 — Retention + downsampling (materialized views rollups, log filter).

### Off-Limits Until Synchronization Gates Pass
- **Off-limits until Gate G2 passes (Wave 3)**:
  - F012 (SLOs & error budgets) — requires F011 alerting engine.
  - F013 (Paging path / ServiceNow) — requires F011 firing alerts.
  - F015 (Multi-tenancy & quotas) — requires F014 retention & downsampling views.
  - F017 (RUM & session replay) — requires Wave 2 completion.
  - F018 (Synthetics) — requires F011 alerting routing.
- **Off-limits until Gate G3 passes (Wave 4)**:
  - F016 (SSO / RBAC via IdP) — requires F015 tenant boundaries.
  - F019 (Anomaly detection) — requires F009 metric streams and F011 alert framework.
  - F020 (Alert correlation) — requires F011, F013, and F019.
- **Off-limits until Gate G4 passes (Wave 5)**:
  - F021 (NL query & incident summarization) — requires F014, F016, F019, F020.

## Rules of the guard
1. If a task tempts you outside the active wave or violates track boundaries, stop.
2. Concurrent subagents work ONLY on their assigned track and active wave features.
3. No dependency unless the active feature needs it — record new deps in the sprint contract
   with a justification. Every image/chart must be mirrored internally (air-gap rule).
4. Do not advance past synchronization gates (G1 -> G2 -> G3 -> G4 -> G5) until all features in the wave pass full verification and evaluator scoring.
