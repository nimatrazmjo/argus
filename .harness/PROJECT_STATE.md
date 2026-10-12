# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 01 — Foundation
- **Active feature**: F002 — ClickHouse HA + object-storage tier (IN PROGRESS)
- **Overall progress**: 1 / 21 features COMPLETE (5%)

## Last verified
- **Date**: 2026-10-12
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, 7 CRDs, 3 operator deployments Ready, image origins)
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (check-architecture + test-edge-cases + init)
- **E2E**: N/A — not user-facing (operator infrastructure baseline verified by init smoke and CRD presence)
- **Git**: branch `feat/F001`

## Next step
Write the sprint contract for F002 (`verification/sprint-contract.md`), then implement
the declarative ClickHouseInstallation CR manifest using Altinity operator schema with 2 shards/replicas,
configure S3/MinIO cold-storage tiering policy, and test persistence across pod restarts. See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None. Internal image mirror (`localhost:5001`) is running with all verified images seeded.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**.
- Baseline operators for OpenTelemetry (0.160.0), Altinity ClickHouse (0.27.4), and Prometheus (v0.94.1) are deployed and Ready in `argus-system`.
- Air-gap compliance is enforced: 100% of container images in `argus-system` resolve from `localhost:5001/argus/...`.
- `deploy/mirror/setup-mirror.sh` and `deploy/mirror/images.txt` maintain the air-gapped catalog.
- Toolchain commands and verification scripts (`init.sh`, `verify.sh`, `test-edge-cases.sh`, `check-architecture.sh`, `deploy-operators.sh`) are implemented and documented in `CLAUDE.md`.
