# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 01 — Foundation
- **Active feature**: F005 — PII/CJIS redaction at ingest (IN PROGRESS)
- **Overall progress**: 4 / 21 features COMPLETE (19%)

## Last verified
- **Date**: 2026-10-12
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, 7 CRDs, 3 operator deployments Ready, ClickHouse HA Completed & Ready, ClickHouse Keeper Ready, OpenTelemetry Gateway & Node DaemonSet Ready, Sample Instrumented Service Ready, 100% mirrored image origins)
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (all 9 steps: check-architecture + test-edge-cases + test-clickhouse-tiering + test-clickhouse-edge-cases + test-otel-pipeline + test-otel-edge-cases + test-correlation + test-correlation-edge-cases + init)
- **E2E**: PASS — `scripts/test-correlation.sh` proves end-to-end trace + metric + log correlation joined on TraceId in ClickHouse with latency < 10s (measured 2s).
- **Git**: branch `feat/F004` -> ready to commit and switch to `feat/F005`

## Next step
Write sprint contract for F005 (`verification/sprint-contract.md`), then implement the
PII/CJIS redaction processor in the OpenTelemetry Collector gateway pipeline:
- Transform/redaction processor configured with declarative rules to mask/strip sensitive fields (SSN, credit card, passwords, CJIS-restricted identifiers) across logs, trace attributes, and span events.
- Test proving sensitive fields present in OTLP input are provably absent from ClickHouse storage.
- Edge cases covering nested attributes, log body vs attribute redaction, and drop-on-failure safety.
See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None. Internal image mirror (`localhost:5001`) and ClickHouse HA cluster are healthy and ready.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**.
- Baseline operators for OpenTelemetry (0.160.0), Altinity ClickHouse (0.27.4), and Prometheus (v0.94.1) are deployed and Ready in `argus-system`.
- Air-gap compliance is enforced: 100% of container images in `argus-system` resolve from `localhost:5001/argus/...`.
- `deploy/mirror/setup-mirror.sh` and `deploy/mirror/images.txt` maintain the air-gapped catalog.
- Toolchain commands and verification scripts (`init.sh`, `verify.sh`, `test-edge-cases.sh`, `check-architecture.sh`, `deploy-operators.sh`) are implemented and documented in `CLAUDE.md`.
