# Phase 03 — Operational layer

Turn visibility into operations: alerting, SLOs, paging, cost control, tenancy, and auth. This
is where the platform becomes safe to run for 50 apps and defensible at ATO.
Execution architecture is governed by [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md).

---

## F011 — Alerting / monitors
- **Execution Mode**: `[PARALLEL TRACK B]` (Incident & Operational Lifecycle — Wave 2 Active)
- **Track**: Track B (Incident & Operational Lifecycle)
- **Wave**: Wave 2
- **Must wait for**: F006 (Sync Gate G1)
- **Can run in parallel with**: F009, F010, F014
- **Blocks**: F012, F013, F018, F019, F020
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Threshold monitors with firing-state management and dedup; an alert fires on a breach and resolves on recovery.
- [ ] Monitors defined declaratively (as code), not click-only.
- [ ] Edge cases: flapping (dedup/hysteresis), missing data, monitor on high-cardinality query.
- [ ] E2E: induce a breach -> alert fires -> recovery -> resolves.
- [ ] FULL verify green.

### Evidence expected
Alert rule manifests; alert fire/resolve transcript under `.harness/evidence/F011/`.

---

## F012 — SLOs + error budgets
- **Execution Mode**: `[PARALLEL TRACK B]` (Incident & Operational Lifecycle — Wave 3)
- **Track**: Track B (Incident & Operational Lifecycle)
- **Wave**: Wave 3
- **Must wait for**: F011 (Requires alert evaluation engine and SLI calculation)
- **Can run in parallel with**: F013, F015, F017, F018
- **Blocks**: None
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Define an SLI/SLO for the sample service; error budget tracked and burn visible.
- [ ] Edge cases: no-traffic window, budget-exhausted state.
- [ ] E2E: SLO page shows budget consumption after induced errors.
- [ ] FULL verify green.

### Evidence expected
SLO definition manifests; budget consumption calculation output under `.harness/evidence/F012/`.

---

## F013 — Paging path
- **Execution Mode**: `[PARALLEL TRACK B]` (Incident & Operational Lifecycle — Wave 3)
- **Track**: Track B (Incident & Operational Lifecycle)
- **Wave**: Wave 3
- **Must wait for**: F011 (Requires firing alert events)
- **Can run in parallel with**: F012, F015, F017, F018
- **Blocks**: F020 (Incident grouping requires incident record destination)
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] A firing alert routes via webhook to the agency incident tool (ServiceNow); payload verified. Optional Keep for correlation in front.
- [ ] Air-gapped: no dependency on any cloud pager.
- [ ] Edge cases: webhook endpoint down (retry/queue), duplicate suppression.
- [ ] E2E: alert -> incident record created downstream (or a stubbed receiver asserts the payload).
- [ ] FULL verify green.

### Evidence expected
Webhook dispatcher configuration; incident payload assertion transcript under `.harness/evidence/F013/`.

---

## F014 — Retention + downsampling (cost control)
- **Execution Mode**: `[PARALLEL TRACK C]` (Data Governance & Storage — Wave 2 Active)
- **Track**: Track C (Data Governance, Storage & Security)
- **Wave**: Wave 2
- **Must wait for**: F002, F006 (Sync Gate G1)
- **Can run in parallel with**: F009, F010, F011
- **Blocks**: F015, F021
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Tiered retention: hot local for N days, cold to S3/MinIO, TTL drop after the window.
- [ ] Metric downsampling via materialized views (raw -> 1m -> 1h rollups).
- [ ] A default log-level filter at the collector so a debug-logging app cannot balloon storage.
- [ ] Edge cases: TTL on a large table, rollup correctness, filter override per service.
- [ ] E2E: `N/A — not user-facing` (asserted by retention/rollup checks on seeded data).
- [ ] FULL verify green.

### Evidence expected
ClickHouse TTL configuration SQL; materialized view schemas; part movement transcript; log-level drop proof under `.harness/evidence/F014/`.

---

## F015 — Multi-tenancy + cardinality guardrails
- **Execution Mode**: `[PARALLEL TRACK C]` (Data Governance & Storage — Wave 3)
- **Track**: Track C (Data Governance, Storage & Security)
- **Wave**: Wave 3
- **Must wait for**: F014 (Builds on storage policies and downsampling partitions)
- **Can run in parallel with**: F012, F013, F017, F018
- **Blocks**: F016 (Tenant isolation primitives prerequisite for RBAC scoping)
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Per-tenant isolation (tenant_id row policies and/or DB separation) and per-tenant ingest quotas.
- [ ] Metric relabeling drops/limits high-cardinality labels at the collector before storage.
- [ ] Edge cases: tenant over quota (throttled, not fatal), cardinality explosion blocked.
- [ ] E2E: `N/A — not user-facing` (asserted by isolation + quota + cardinality tests).
- [ ] FULL verify green.

### Evidence expected
Row policy SQL / quota manifests; collector relabeling config; throttle/drop transcripts under `.harness/evidence/F015/`.

---

## F016 — SSO / RBAC via agency IdP
- **Execution Mode**: `[PARALLEL TRACK C]` (Data Governance & Security — Wave 4)
- **Track**: Track C (Data Governance, Storage & Security)
- **Wave**: Wave 4
- **Must wait for**: F015 (Requires multi-tenant boundaries for scoped roles)
- **Can run in parallel with**: F019, F020
- **Blocks**: F021 (NL query requires RBAC permission enforcement)
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] UI auth via SAML/OIDC against the agency IdP (PIV/CAC-backed where required); roles mapped (viewer/operator/admin).
- [ ] Confirm which auth/RBAC features are in the OSS build vs enterprise, recorded as a decision (`ADR-0007-sso-rbac-idp.md`).
- [ ] Edge cases: failed auth, role with no access, token expiry.
- [ ] E2E: a scoped user logs in and sees only their permitted scope.
- [ ] FULL verify green.

### Evidence expected
IdP configuration manifests; RBAC mapping proof; login session transcript under `.harness/evidence/F016/`.

---

## Wave Synchronization Gates
- **Wave 2 Gate (Gate G2)**: F011 (Alerting) and F014 (Retention) must pass full verification alongside F009 and F010 before unlocking Wave 3.
- **Wave 3 Gate (Gate G3)**: F012 (SLOs), F013 (Paging), and F015 (Tenancy) must pass alongside F017 and F018 before unlocking Wave 4.
- **Wave 4 Gate (Gate G4)**: F016 (SSO/RBAC) must pass alongside F019 and F020 before unlocking Wave 5.
