# CURRENT TASK

**Feature**: F002 — ClickHouse HA + object-storage tier
**Phase**: Phase 01 — Foundation
**Status**: IN PROGRESS

## Exact next step
1. Write `verification/sprint-contract.md` for F002, mapping each acceptance item in
   `phases/PHASE-01-FOUNDATION.md` to a concrete check.
2. Define declarative ClickHouseInstallation CR manifest using Altinity operator schema with 2 shards/replicas.
3. Configure local S3/MinIO tiered storage policy and automated part tiering verification.
4. Implement resilience tests (insert -> restart pod -> verify persistence, edge cases).

## Acceptance (summary)
See `phases/PHASE-01-FOUNDATION.md` -> F002 for full criteria and the signed
`verification/sprint-contract.md` for this feature.

## Definition of done
Every acceptance item met + evidence in `CHANGELOG.md` + Evaluator PASS + check-architecture
clean + PR reviewed clean (inert until a remote + gh exist). See `AGENTS.md`.
