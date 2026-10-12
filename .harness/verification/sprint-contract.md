# Sprint Contract — F005: PII/CJIS redaction at ingest

Feature: F005 — PII/CJIS redaction at ingest
Phase: Phase 01 — Foundation
Date: 2026-10-12

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] Declarative redaction/transform processor configured in the OpenTelemetry Gateway collector pipeline (`deploy/otel/gateway.yaml`):
  - Strips agreed sensitive keys (`ssn`, `password`, `secret`, `token`, `auth_token`, `api_key`, `cjis_fbi_number`, `credit_card`).
  - Masks pattern-matched sensitive values in freeform attributes and log bodies (SSN: `\d{3}-\d{2}-\d{4}` -> `[REDACTED_SSN]`, PAN/Credit Card: `\b(?:\d[ -]*?){13,16}\b` -> `[REDACTED_PAN]`).
  - Config is human-reviewable by compliance officers (clean, explicit field list and named rules).
- [x] Redaction applies across all signals:
  - Logs: log attributes, log body.
  - Traces: span attributes.
  - Span events: event attributes.
- [x] Proof of absence: An automated test script (`scripts/test-redaction.sh`) emits OTLP traces, span events, and logs containing sensitive fields/PII:
  - Asserts sensitive values land nowhere in ClickHouse (`otel_traces`, `otel_logs`, `Events.Attributes`, etc.).
  - Asserts non-sensitive fields and trace context are intact and correlated.
- [x] Edge cases covered (`scripts/test-redaction-edge-cases.sh`):
  - **Field in log body vs log attribute**: Sensitive data in both message body and attribute map are redacted simultaneously.
  - **Span event attributes**: Sensitive data attached to an in-span event (`Events.Attributes`) is scrubbed.
  - **Multiple occurrences & formats**: Multiple PII instances in a single log message or mixed with valid text are redacted.
  - **Safe degradation / drop-not-leak**: Redaction processor failure mode does not leak unredacted data downstream.
- [x] E2E integration: Sample service emits request containing PII attributes and body; ClickHouse query confirms telemetry is ingested, correlated, and scrubbed.
- [x] Air-gap compliance: 100% of container images resolved from internal mirror (`localhost:5001/argus/*`).
- [x] No regressions: `./scripts/verify.sh` green (all 11 steps pass).

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
- **Input / data**:
  - Embedded PII in log body string (e.g. `User SSN 123-45-6789 submitted payment`) -> body replaced with `[REDACTED_SSN]`.
  - Sensitive key in span event -> deleted / masked in `Events.Attributes`.
  - Empty or non-string attribute values -> processor executes without throwing uncaught exceptions.
- **Compliance / security**:
  - Sensitive fields never persist to ClickHouse hot or cold storage.
  - Explicit blacklist for keys + regex patterns for unstructured values.

## 3. E2E scenario(s)
An application or client emits a transaction containing:
- Span attributes: `ssn: "123-45-6789"`, `password: "SuperSecret123"`, `order.id: "ord-99"`.
- Span event: name `auth_attempt`, event attributes `auth_token: "bearer-xyz123"`.
- Log record: attribute `cjis_fbi_number: "FBI-987654321"`, body `Payment processed for card 4111-2222-3333-4444`.
Collector gateway processes the stream:
- `ssn` and `password` removed from span attributes.
- `auth_token` removed from span event attributes.
- `cjis_fbi_number` removed from log attributes.
- Card number in log body replaced with `[REDACTED_PAN]`.
ClickHouse is queried:
- Returns zero rows where any table contains `123-45-6789`, `SuperSecret123`, `bearer-xyz123`, `FBI-987654321`, or `4111-2222-3333-4444`.
- Trace, log, and metric remain queryable and correlated.

## 4. Plan (thinnest vertical slice)
1. Add `transform` processor configuration to `deploy/otel/gateway.yaml` with compliance-reviewable statements for traces, logs, and span events.
2. Deploy updated gateway configuration via `kubectl apply -f deploy/otel/gateway.yaml` and wait for rollout.
3. Create automated redaction test script `scripts/test-redaction.sh`:
   - Emits test trace with sensitive span attributes and span events.
   - Emits test log with sensitive log attributes and PII body.
   - Queries ClickHouse and asserts sensitive strings are 100% absent, while redacted markers and non-sensitive fields are present.
4. Create automated redaction edge cases test script `scripts/test-redaction-edge-cases.sh`.
5. Enhance sample service `server.py` and `scripts/test-correlation.sh` to optionally inject PII and verify redaction during end-to-end flow.
6. Integrate into `scripts/verify.sh` as steps in full verification suite.
7. Verify all edge cases and air-gap audit, update documentation and commit.

## 5. Out of scope (parked, not built)
- UI visualization in SigNoz (Phase 02, F006).
- Mutating webhook auto-injection (Phase 02, F007).
