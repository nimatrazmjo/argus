# CURRENT TASK

**Feature**: F001 — Cluster baseline + operators
**Phase**: Phase 01 — Foundation
**Status**: IN PROGRESS

## Exact next step
1. Write `verification/sprint-contract.md` for F001, mapping each acceptance item in
   `phases/PHASE-01-FOUNDATION.md` to a concrete check.
2. Create `scripts/init.sh` (validate cluster access + required CRDs + operators Ready) and
   `scripts/check-architecture.sh` (no-op exit 0 until layer-boundaries is filled).
3. Add the Helm install (declarative values / GitOps) for the OpenTelemetry Operator, the
   Altinity ClickHouse operator, and the Prometheus Operator — all images from the internal
   mirror, no public-registry pulls.

## Acceptance (summary)
See `phases/PHASE-01-FOUNDATION.md` -> F001 for full criteria and the signed
`verification/sprint-contract.md` for this feature.

## Definition of done
Every acceptance item met + evidence in `CHANGELOG.md` + Evaluator PASS + check-architecture
clean (no-op for now) + PR reviewed clean (inert until a remote + gh exist). See `AGENTS.md`.
