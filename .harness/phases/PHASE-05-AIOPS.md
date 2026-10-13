# Phase 05 — AIOps / the moat

The differentiated layer — anomaly detection, correlation, and an LLM query/summary surface.
Deferred and optional; the platform is fully useful without it.
Execution architecture is governed by [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md).

---

## F019 — Anomaly + forecast monitors
- **Execution Mode**: `[PARALLEL TRACK E]` (AIOps & Intelligence — Wave 4)
- **Track**: Track E (AIOps & Intelligence Layer)
- **Wave**: Wave 4
- **Must wait for**: F009 (Infra metric streams), F011 (Alerting framework), Sync Gate G3
- **Can run in parallel with**: F016, F020 (pipelined)
- **Blocks**: F020, F021
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] At least one metric has a dynamic monitor (seasonal decomposition or EWMA baseline) that fires on true anomalies, not fixed thresholds.
- [ ] Measured false-positive rate on a replayed week of data is reported.
- [ ] Edge cases: seasonality shift, sparse data, cold start.
- [ ] E2E: injected anomaly fires; normal variation does not.
- [ ] FULL verify green.

### Evidence expected
Dynamic monitor algorithms; false-positive benchmark report; anomaly firing transcript under `.harness/evidence/F019/`.

---

## F020 — Alert correlation + root-cause grouping
- **Execution Mode**: `[PARALLEL TRACK E]` (AIOps & Intelligence — Wave 4)
- **Track**: Track E (AIOps & Intelligence Layer)
- **Wave**: Wave 4
- **Must wait for**: F011 (Alert events), F013 (Incident records), F019 (Anomaly alerts), Sync Gate G3
- **Can run in parallel with**: F016
- **Blocks**: F021 (Incident correlation graph required for summarization)
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Related alerts across services group into one incident with a probable-cause ranking using topology from F007/F008.
- [ ] Edge cases: unrelated-but-simultaneous alerts not falsely merged.
- [ ] E2E: a cascading failure produces one grouped incident, not N pages.
- [ ] FULL verify green.

### Evidence expected
Correlation rules/engine manifests; grouped incident payload transcript under `.harness/evidence/F020/`.

---

## F021 — NL query + incident summarization (LLM)
- **Execution Mode**: `[SEQUENTIAL GATE]` (Wave 5 Final Moat)
- **Track**: Track E (AIOps & Intelligence Layer)
- **Wave**: Wave 5
- **Must wait for**: F014 (Data schemas/rollups), F016 (RBAC boundaries), F019 (Anomaly metrics), F020 (Correlated incident graph), Sync Gate G4
- **Can run in parallel with**: None (Final sequential integration gate before full ATO sign-off)
- **Blocks**: Full DHS Platform Certification & ATO Readiness
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] A natural-language query returns the right telemetry (NL -> ClickHouse SQL) for a defined question set; incidents get an auto-summary.
- [ ] LLM backend runs within the agency boundary (Bedrock in the approved GovCloud boundary, or an on-prem model) — no data leaves the boundary.
- [ ] Strictly respects RBAC roles established in F016.
- [ ] Edge cases: ambiguous query, hallucinated field rejected, prompt-injection from log content neutralized.
- [ ] E2E: the query set returns correct results; an incident summary is generated.
- [ ] FULL verify green.

### Evidence expected
NL-to-SQL translation benchmarks; GovCloud Bedrock egress test proof; incident summary output under `.harness/evidence/F021/`.

---

## Wave Synchronization Gates
- **Wave 4 Gate (Gate G4)**: F016 (SSO/RBAC), F019 (Anomaly Monitors), and F020 (Alert Correlation) must complete with full verification before unlocking Wave 5.
- **Wave 5 Gate (Gate G5)**: F021 (NL Query / Summarization) completes as the final sequential integration gate, validating full platform compliance and ATO readiness.
