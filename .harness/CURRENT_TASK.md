# CURRENT TASK

**Feature**: F006 — SigNoz UI over ClickHouse
**Phase**: Phase 02 — Coverage
**Status**: COMPLETE

## Completed steps
1. Sprint contract written in `verification/sprint-contract.md`.
2. Verified latest images mirrored to air-gapped registry `localhost:5001/argus/*`:
   - `signoz/signoz:v0.145.0`
   - `signoz/signoz-otel-collector:v0.144.13`
   - `clickhouse/clickhouse-server:25.12.5`
3. ClickHouse HA cluster upgraded to 25.12.5 with `cluster` alias, inter-node auth, and experimental JSON settings.
4. SigNoz schema migrations executed cleanly across all signal tables (`signoz_traces`, `signoz_logs`, `signoz_metrics`, `signoz_meter`, `signoz_metadata`, `signoz_analytics`).
5. SigNoz collector (`deploy/signoz/signoz-otel-collector.yaml`) and SigNoz server (`deploy/signoz/signoz.yaml`) deployed and running healthy.
6. OpenTelemetry Gateway configured to forward redacted telemetry to SigNoz collector.
7. Declarative deployer `scripts/deploy-signoz.sh`, functional verification `scripts/test-signoz.sh`, and edge cases `scripts/test-signoz-edge-cases.sh` implemented and passing.
8. Full 13-step `./scripts/verify.sh` test suite green with zero regressions.
9. Verification evidence captured in `.harness/evidence/F006/`.

## Next step
Commit F006 on branch `feat/F006`, merge or advance to next feature `F007` (Zero-code auto-instrumentation via OTel Operator annotation + onboarding runbook for app teams).
