# PROJECT STATE — MASTER FILE

> Read this first, every session. Rewrite it for a cold reader before you stop.

## Where we are
- **Phase**: Phase 02 — Coverage
- **Active feature**: F007 — Zero-code auto-instrumentation via OTel Operator annotation; onboarding runbook for app teams (COMPLETE)
- **Overall progress**: 7 / 21 features COMPLETE (33%)
- **Milestone status**: Phase 01 (Foundation: F001-F005) is 100% COMPLETE. F006 and F007 are 100% COMPLETE.

## Last verified
- **Date**: 2026-10-13
- **init**: PASS — `scripts/init.sh` green (validates cluster v1.36.1, mirror health, 7 CRDs, 3 operator deployments Ready, ClickHouse HA Completed & Ready, ClickHouse Keeper Ready, OpenTelemetry Gateway & Node DaemonSet Ready, Sample Instrumented Service Ready, SigNoz UI & Collector Ready, 100% mirrored image origins)
- **Full suite + check-architecture**: PASS — `scripts/verify.sh` green (all 15 steps: check-architecture + test-edge-cases + test-clickhouse-tiering + test-clickhouse-edge-cases + test-otel-pipeline + test-otel-edge-cases + test-correlation + test-correlation-edge-cases + test-redaction + test-redaction-edge-cases + test-signoz + test-signoz-edge-cases + test-auto-instrumentation + test-auto-instrumentation-edge-cases + init)
- **E2E**: PASS — Zero-code auto-instrumentation end-to-end verified with Trace ID generation, ClickHouse ingestion, SigNoz service catalog discovery, and trace query.
- **Git**: branch `feat/F007` -> ready to commit

## Next step
Begin Feature F008 — eBPF safety net (Beyla): network-level service map for un-annotated services:
- Mirror Grafana Beyla (`grafana/beyla:2.2.4` -> `localhost:5001/argus/beyla:2.2.4`) and update `deploy/mirror/images.txt`.
- Record ADR-0005 (`docs/decisions/ADR-0005-ebpf-safety-net-beyla.md`).
- Deploy Beyla DaemonSet (`deploy/ebpf/beyla.yaml`).
- Write `scripts/test-ebpf.sh` and `scripts/test-ebpf-edge-cases.sh`.
- Update `scripts/verify.sh`.
See CURRENT_TASK.md.

## Open blockers
See `BLOCKERS.md`. None. Internal image mirror (`localhost:5001`) and ClickHouse HA cluster are healthy and ready.

## Notes for the next agent
- Archetype is **DevOps/IaC (archetype B)**.
- Baseline operators for OpenTelemetry (0.160.0), Altinity ClickHouse (0.27.4), and Prometheus (v0.94.1) are deployed and Ready in `argus-system`.
- Air-gap compliance is enforced: 100% of container images in `argus-system` resolve from `localhost:5001/argus/...`.
- `deploy/mirror/setup-mirror.sh` and `deploy/mirror/images.txt` maintain the air-gapped catalog.
- Toolchain commands and verification scripts (`init.sh`, `verify.sh`, `test-edge-cases.sh`, `check-architecture.sh`, `deploy-operators.sh`) are implemented and documented in `CLAUDE.md`.
