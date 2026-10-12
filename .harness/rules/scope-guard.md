# Scope Guard

What is **off-limits right now**. Scope creep is the most common agent failure; this file is
the leash. The active phase is whatever `PROJECT_STATE.md` says. Building ahead of it is a
defect, not initiative. Phases are gated (ROADMAP.md order); a phase's features may not start
until the previous phase's completion criteria pass.

## Current phase: Phase 01 — Foundation

### In scope (current phase only)
- F001 — operators installed from a mirrored internal registry; `init.sh` + `check-architecture.sh`.
- F002 — ClickHouse HA with S3/MinIO-backed storage policy.
- F003 — OTel Collector pipeline (node DaemonSet + gateway), OTLP -> ClickHouse, k8s enrichment.
- F004 — end-to-end metric+trace+log correlation by trace id, with an e2e test.
- F005 — PII/CJIS redaction at ingest, provable.

### Off-limits until their phase (do NOT build now)
- Phase 02 (Coverage): SigNoz UI rollout, auto-instrumentation/onboarding, eBPF service maps,
  infra metrics, profiling. Resist wiring the UI or auto-instrumentation before the raw spine
  is proven end to end.
- Phase 03 (Operational): alerting, SLOs, paging/ServiceNow, retention/downsampling,
  multi-tenancy, SSO/RBAC. Do not add alert rules or tenancy before coverage exists.
- Phase 04 (Frontend signals): RUM, session replay, synthetics.
- Phase 05 (AIOps): anomaly/forecast, correlation/root-cause, NL/LLM query.

## Rules of the guard
1. If a task tempts you outside the current phase, stop. Note it in `BLOCKERS.md` (or as a
   future feature in `ROADMAP.md`) and keep going on the active feature.
2. No dependency unless the active feature needs it — record new deps in the sprint contract
   with a justification. Every image/chart must be mirrored internally (air-gap rule).
3. Design *for* later phases (stable ids, registries, interfaces) but *build* only the current
   phase.
4. If scope is wrong, propose an edit to this file + `ROADMAP.md` — don't silently expand.
   Record the decision in `DECISIONS.md`.
5. Don't skip a phase's completion criteria. A phase is done only when every feature is
   `COMPLETE` with evidence and the phase smoke test is green.

## Why so strict
A solid, tested foundation beats half of every phase started. The observability spine
(collector + store + correlation) is early substrate; its shakiness multiplies across
everything built on top of it.
