# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 02 — Coverage
- **Active feature**: F006 — SigNoz deployed, reading ClickHouse: APM, logs, traces, dashboards (IN PROGRESS)
- **Overall progress**: 5 / 21 features COMPLETE (24%)
- **Milestone status**: Phase 01 (Foundation: F001-F005) is 100% COMPLETE.

## Last verified
- **Date**: 2026-10-12
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, 7 CRDs, 3 operator deployments Ready, ClickHouse HA Completed & Ready, ClickHouse Keeper Ready, OpenTelemetry Gateway & Node DaemonSet Ready, Sample Instrumented Service Ready, 100% mirrored image origins)
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (all 11 steps: check-architecture + test-edge-cases + test-clickhouse-tiering + test-clickhouse-edge-cases + test-otel-pipeline + test-otel-edge-cases + test-correlation + test-correlation-edge-cases + test-redaction + test-redaction-edge-cases + init)
- **E2E**: PASS — Full Phase 01 smoke test passed (init green + correlated, redacted metric+trace+log).
- **Git**: branch `feat/F005` -> ready to commit and switch to `feat/F006`

## Next step
Write sprint contract for F006 (`verification/sprint-contract.md`), then deploy SigNoz
(frontend, query-service) into `argus-system` connected to our existing ClickHouse HA cluster:
- Mirror latest verified SigNoz images (`signoz/frontend`, `signoz/query-service`) to `localhost:5001/argus/*`.
- Deploy SigNoz pointing to `clickhouse-argus-clickhouse:9000` with user `default` and password `argus123`.
- Verify SigNoz UI and API read traces, logs, and metrics directly from ClickHouse.
See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None. Internal image mirror (`localhost:5001`) and ClickHouse HA cluster are healthy and ready.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**.
- Baseline operators for OpenTelemetry (0.160.0), Altinity ClickHouse (0.27.4), and Prometheus (v0.94.1) are deployed and Ready in `argus-system`.
- Air-gap compliance is enforced: 100% of container images in `argus-system` resolve from `localhost:5001/argus/...`.
- `deploy/mirror/setup-mirror.sh` and `deploy/mirror/images.txt` maintain the air-gapped catalog.
- Toolchain commands and verification scripts (`init.sh`, `verify.sh`, `test-edge-cases.sh`, `check-architecture.sh`, `deploy-operators.sh`) are implemented and documented in `CLAUDE.md`.
