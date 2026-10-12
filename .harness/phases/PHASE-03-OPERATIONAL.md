# Phase 03 — Operational layer

Turn visibility into operations: alerting, SLOs, paging, cost control, tenancy, and auth. This
is where the platform becomes safe to run for 50 apps and defensible at ATO. Depends on green
Phase 02.

## F011 — Alerting / monitors
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Threshold monitors with firing-state management and dedup; an alert fires on a breach and resolves on recovery.
- [ ] Monitors defined declaratively (as code), not click-only.
- [ ] Edge cases: flapping (dedup/hysteresis), missing data, monitor on high-cardinality query.
- [ ] E2E: induce a breach -> alert fires -> recovery -> resolves.
- [ ] FULL verify green.

## F012 — SLOs + error budgets
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Define an SLI/SLO for the sample service; error budget tracked and burn visible.
- [ ] Edge cases: no-traffic window, budget-exhausted state.
- [ ] E2E: SLO page shows budget consumption after induced errors.
- [ ] FULL verify green.

## F013 — Paging path
**Status**: NOT STARTED
### Acceptance criteria
- [ ] A firing alert routes via webhook to the agency incident tool (ServiceNow); payload verified. Optional Keep for correlation in front.
- [ ] Air-gapped: no dependency on any cloud pager.
- [ ] Edge cases: webhook endpoint down (retry/queue), duplicate suppression.
- [ ] E2E: alert -> incident record created downstream (or a stubbed receiver asserts the payload).
- [ ] FULL verify green.

## F014 — Retention + downsampling (cost control)
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Tiered retention: hot local for N days, cold to S3/MinIO, TTL drop after the window.
- [ ] Metric downsampling via materialized views (raw -> 1m -> 1h rollups).
- [ ] A default log-level filter at the collector so a debug-logging app cannot balloon storage.
- [ ] Edge cases: TTL on a large table, rollup correctness, filter override per service.
- [ ] E2E: `N/A` — asserted by retention/rollup checks on seeded data.
- [ ] FULL verify green.

## F015 — Multi-tenancy + cardinality guardrails
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Per-tenant isolation (tenant_id row policies and/or DB separation) and per-tenant ingest quotas.
- [ ] Metric relabeling drops/limits high-cardinality labels at the collector before storage.
- [ ] Edge cases: tenant over quota (throttled, not fatal), cardinality explosion blocked.
- [ ] E2E: `N/A` — asserted by isolation + quota + cardinality tests.
- [ ] FULL verify green.

## F016 — SSO / RBAC via agency IdP
**Status**: NOT STARTED
### Acceptance criteria
- [ ] UI auth via SAML/OIDC against the agency IdP (PIV/CAC-backed where required); roles mapped (viewer/operator/admin).
- [ ] Confirm which auth/RBAC features are in the OSS build vs enterprise, recorded as a decision.
- [ ] Edge cases: failed auth, role with no access, token expiry.
- [ ] E2E: a scoped user logs in and sees only their permitted scope.
- [ ] FULL verify green.

## Phase completion criteria
F011-F016 all `COMPLETE` with evidence; alerts page out, cost is bounded by retention+rollups,
tenants are isolated, and auth ties to the IdP; phase smoke green.
