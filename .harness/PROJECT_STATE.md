# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 02 — Coverage
- **Active feature**: F006 — SigNoz deployed, reading ClickHouse: APM, logs, traces, dashboards (COMPLETE)
- **Overall progress**: 6 / 21 features COMPLETE (29%)
- **Milestone status**: Phase 01 (Foundation: F001-F005) is 100% COMPLETE. F006 is 100% COMPLETE.

## Last verified
- **Date**: 2026-10-12
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, 7 CRDs, 3 operator deployments Ready, ClickHouse HA Completed & Ready, ClickHouse Keeper Ready, OpenTelemetry Gateway & Node DaemonSet Ready, Sample Instrumented Service Ready, SigNoz UI & Collector Ready, 100% mirrored image origins)
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (all 13 steps: check-architecture + test-edge-cases + test-clickhouse-tiering + test-clickhouse-edge-cases + test-otel-pipeline + test-otel-edge-cases + test-correlation + test-correlation-edge-cases + test-redaction + test-redaction-edge-cases + test-signoz + test-signoz-edge-cases + init)
- **E2E**: PASS — SigNoz APM, traces, logs query, and air-gap verification green.
- **Git**: branch `feat/F006` -> ready to commit

## Next step
Begin Feature F007 — Zero-code auto-instrumentation via OTel Operator annotation + onboarding runbook for app teams:
- Create `Instrumentation` CR for auto-instrumentation (Python/Java/Node) in `deploy/otel/instrumentation.yaml`.
- Add auto-instrumentation pod annotation to sample workload.
- Verify traces and metrics appear in SigNoz without manual code instrumentation.
- Write runbook for application teams.
See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None. Internal image mirror (`localhost:5001`) and ClickHouse HA cluster are healthy and ready.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**.
- Baseline operators for OpenTelemetry (0.160.0), Altinity ClickHouse (0.27.4), and Prometheus (v0.94.1) are deployed and Ready in `argus-system`.
- Air-gap compliance is enforced: 100% of container images in `argus-system` resolve from `localhost:5001/argus/...`.
- `deploy/mirror/setup-mirror.sh` and `deploy/mirror/images.txt` maintain the air-gapped catalog.
- Toolchain commands and verification scripts (`init.sh`, `verify.sh`, `test-edge-cases.sh`, `check-architecture.sh`, `deploy-operators.sh`) are implemented and documented in `CLAUDE.md`.
