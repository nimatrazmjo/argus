# ADR-0010: Multi-Tenancy Isolation, Resource Quotas & Ingest Cardinality Guardrails

## Status
Accepted

## Context
As Argus expands across DHS operational divisions (Feature F015), multiple agencies and program offices share the telemetry platform. In federal multi-tenant deployments:
1. Strict data isolation is mandatory: Tenant Alpha must never view Tenant Beta's traces, logs, or metrics.
2. Noisy-neighbor protection is required: one tenant executing unbounded analytical queries must not exhaust ClickHouse CPU or memory, degrading performance for other tenants.
3. High-cardinality metric attacks or developer bugs (e.g., placing UUIDs, user IDs, or timestamps in Prometheus metric label keys) cause combinatorial explosion in metric series tables (`samples_v4`, `time_series_v4`), which can cause database Out-Of-Memory (OOM) failures.

## Decision
1. **ClickHouse Row-Level Security (RLS)**:
   - Implement ClickHouse Row Policies (`CREATE ROW POLICY ... ON default.otel_* FOR SELECT USING ... TO <tenant>`).
   - Tenant users authenticate with distinct credentials (`tenant_alpha`, `tenant_beta`).
   - The query engine automatically injects the row policy filter:
     `ResourceAttributes['tenant_id'] = currentUser() OR currentUser() = 'default'`
   - Tenant isolation is strictly enforced at the database kernel level, rendering cross-tenant data leakage impossible even if a tenant sends raw SQL.
2. **ClickHouse Query Quotas**:
   - Configure ClickHouse `QUOTA` definitions (`tenant_quota`) assigned to tenant users.
   - Restrict execution limits: max 30 seconds execution time, max 10GB read data, max 5,000,000 read rows per 1-hour tracking interval.
   - If a tenant breaches their quota, ClickHouse raises `QUOTA_EXCEEDED` (code 201/202) for that user only, while neighbor tenants continue without interference.
3. **Ingestion Cardinality Guardrails in OpenTelemetry Collector**:
   - Deploy `transform/cardinality_guardrails` in the gateway collector processor pipeline.
   - Intercept incoming attributes:
     - Automatically redact/delete known exploding high-cardinality keys: `user_guid`, `random_hash`, `session_id`, `request_id`, `transaction_token`.
     - Guarantee tenant attribution: assign `tenant_id = "default"` if omitted.
   - Prevents un-indexed label cardinality storms before writes hit ClickHouse MergeTree storage.

## Consequences
- **Positive**:
  - Cryptographically and logically enforced multi-tenant boundaries.
  - Complete protection against noisy-neighbor analytical denial of service.
  - Elimination of cardinality explosion risks in shared storage engines.
- **Negative / Trade-offs**:
  - Queries by tenant users incur a minor filter check against `ResourceAttributes['tenant_id']`.
