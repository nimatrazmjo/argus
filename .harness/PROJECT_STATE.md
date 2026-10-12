# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 01 — Foundation
- **Active feature**: F003 — OTel Collector pipeline (ingest spine) (IN PROGRESS)
- **Overall progress**: 2 / 21 features COMPLETE (10%)

## Last verified
- **Date**: 2026-10-12
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, 7 CRDs, 3 operator deployments Ready, ClickHouse HA Completed & Ready, ClickHouse Keeper Ready, 100% mirrored image origins)
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (check-architecture + test-edge-cases + test-clickhouse-tiering + test-clickhouse-edge-cases + init)
- **E2E**: N/A — not user-facing (backend data storage tier verified by automated SQL functional test suite)
- **Git**: branch `feat/F002` — working tree clean

## Next step
Write the sprint contract for F003 (`verification/sprint-contract.md`), then implement
the OpenTelemetry Collector pipeline: node-level DaemonSet (kubelet/cAdvisor, filelog receiver, OTLP receiver)
and gateway Deployment (batch, k8sattributes processor, ClickHouse exporter), routing OTLP metrics, logs,
and traces into ClickHouse. See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None. Internal image mirror (`localhost:5001`) and ClickHouse HA cluster are healthy and ready.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**.
- Baseline operators for OpenTelemetry (0.160.0), Altinity ClickHouse (0.27.4), and Prometheus (v0.94.1) are deployed and Ready in `argus-system`.
- Air-gap compliance is enforced: 100% of container images in `argus-system` resolve from `localhost:5001/argus/...`.
- `deploy/mirror/setup-mirror.sh` and `deploy/mirror/images.txt` maintain the air-gapped catalog.
- Toolchain commands and verification scripts (`init.sh`, `verify.sh`, `test-edge-cases.sh`, `check-architecture.sh`, `deploy-operators.sh`) are implemented and documented in `CLAUDE.md`.
