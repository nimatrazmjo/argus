# CURRENT TASK

**Feature**: F005 — PII/CJIS redaction at ingest
**Phase**: Phase 01 — Foundation
**Status**: IN PROGRESS

## Exact next step
1. Commit completed F004 implementation on branch `feat/F004`.
2. Create and checkout git branch `feat/F005`.
3. Write `verification/sprint-contract.md` for F005 mapping acceptance criteria:
   - Redaction/transform processor in OTel gateway pipeline masks/strips sensitive fields (SSN, credit cards, CJIS identifiers, auth tokens, passwords) before ClickHouse export.
   - Test proving sensitive fields present in OTLP input are provably absent from ClickHouse storage.
   - Redaction runs on logs, trace attributes, and span events.
   - Config is reviewable by compliance persona (clear regex/field list rules).
   - Edge cases: nested attributes, field in log body vs attribute, redaction failure drops rather than leaks.
4. Implement redaction processor configuration in `deploy/otel/gateway.yaml` (using `redaction` or `transform` processor).
5. Implement `scripts/test-redaction.sh` and `scripts/test-redaction-edge-cases.sh`.
6. Integrate into `scripts/verify.sh` and run full suite.

## Acceptance (summary)
See `phases/PHASE-01-FOUNDATION.md` -> F005 for full criteria and the signed
`verification/sprint-contract.md` for this feature.

## Definition of done
Every acceptance item met + evidence in `CHANGELOG.md` + Evaluator PASS + check-architecture
clean + PR reviewed clean (inert until a remote + gh exist). See `AGENTS.md`.
