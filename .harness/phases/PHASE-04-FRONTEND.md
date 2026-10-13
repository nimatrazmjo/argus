# Phase 04 — Frontend signals

The signals with no mature OSS equivalent, so the most build-heavy per unit of parity. Depends
on green Phase 03 foundation.
Execution architecture is governed by [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md).

---

## F017 — RUM + session replay
- **Execution Mode**: `[PARALLEL TRACK D]` (Frontend & Synthetic Monitoring — Wave 3)
- **Track**: Track D (Frontend & Synthetic Monitoring)
- **Wave**: Wave 3
- **Must wait for**: F005 (PII redaction standards), F006 (SigNoz UI), Sync Gate G2
- **Can run in parallel with**: F012, F013, F015, F018
- **Blocks**: None
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] RUM + session replay deployed (OpenReplay or HyperDX); a browser session is captured and replayable for a sample frontend.
- [ ] Decision (OpenReplay vs HyperDX, and whether it replaces or sits beside SigNoz) recorded as an ADR.
- [ ] PII in the session (form fields) masked, consistent with F005 redaction posture.
- [ ] Air-gapped images mirrored to internal registry.
- [ ] Edge cases: masking correctness, large session, replay with missing assets.
- [ ] E2E: a captured session replays with sensitive fields masked.
- [ ] FULL verify green.

### Evidence expected
RUM ingestion and UI manifests; session replay transcript/screenshot under `.harness/evidence/F017/`; PII masking test verification.

---

## F018 — Synthetics
- **Execution Mode**: `[PARALLEL TRACK D]` (Frontend & Synthetic Monitoring — Wave 3)
- **Track**: Track D (Frontend & Synthetic Monitoring)
- **Wave**: Wave 3
- **Must wait for**: F011 (Requires alerting engine to route failure notifications), Sync Gate G2
- **Can run in parallel with**: F012, F013, F015, F017
- **Blocks**: None
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Blackbox probes for uptime + scheduled Playwright browser checks as CronJobs; results stored and viewable.
- [ ] A failing synthetic raises an alert through the Phase 03 alerting path (F011/F013).
- [ ] Edge cases: probe timeout, check against an auth-walled page, flaky check quarantined at root.
- [ ] E2E: a scheduled check runs, fails on an induced outage, and alerts.
- [ ] FULL verify green.

### Evidence expected
Playwright CronJob manifests; synthetic results schema query output; alert triggering transcript under `.harness/evidence/F018/`.

---

## Wave Synchronization Gates
- **Wave 3 Gate (Gate G3)**: F017 (RUM) and F018 (Synthetics) must complete concurrently with F012 (SLOs), F013 (Paging), and F015 (Tenancy) with all verification suites green before unlocking Wave 4.
