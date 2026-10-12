# CURRENT TASK

**Feature**: F004 — End-to-end correlation proof
**Phase**: Phase 01 — Foundation
**Status**: IN PROGRESS

## Exact next step
1. Commit completed F003 implementation on branch `feat/F003`.
2. Create and checkout git branch `feat/F004`.
3. Write `verification/sprint-contract.md` for F004 mapping acceptance criteria:
   - Sample instrumented app emitting metric, trace, and log with matching TraceID for a single transaction.
   - TraceID present across all three telemetry types.
   - ClickHouse SQL query successfully joins all 3 on TraceID.
   - Latency from emit to ClickHouse queryable < 10 seconds.
   - Automated e2e test script reproduces correlation join query on demand.
4. Deploy sample service / synthetic generator in Kubernetes using mirrored image.
5. Implement `scripts/test-correlation.sh` and edge cases (dropped span, log without trace id, clock skew).
6. Integrate into `scripts/verify.sh`.

## Acceptance (summary)
See `phases/PHASE-01-FOUNDATION.md` -> F004 for full criteria and the signed
`verification/sprint-contract.md` for this feature.

## Definition of done
Every acceptance item met + evidence in `CHANGELOG.md` + Evaluator PASS + check-architecture
clean + PR reviewed clean (inert until a remote + gh exist). See `AGENTS.md`.
