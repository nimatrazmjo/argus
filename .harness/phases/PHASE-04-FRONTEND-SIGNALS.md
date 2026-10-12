# Phase 04 — Frontend signals

The signals with no mature OSS equivalent, so the most build-heavy per unit of parity. Depends
on green Phase 03. Only start if frontend visibility is actually required by the consuming apps.

## F017 — RUM + session replay
**Status**: NOT STARTED
### Acceptance criteria
- [ ] RUM + session replay deployed (OpenReplay or HyperDX); a browser session is captured and replayable for a sample frontend.
- [ ] Decision (OpenReplay vs HyperDX, and whether it replaces or sits beside SigNoz) recorded as an ADR.
- [ ] PII in the session (form fields) masked, consistent with F005 redaction posture.
- [ ] Edge cases: masking correctness, large session, replay with missing assets.
- [ ] E2E: a captured session replays with sensitive fields masked.
- [ ] FULL verify green.

## F018 — Synthetics
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Blackbox probes for uptime + scheduled Playwright browser checks as CronJobs; results stored and viewable.
- [ ] A failing synthetic raises an alert through the Phase 03 path.
- [ ] Edge cases: probe timeout, check against an auth-walled page, flaky check quarantined at root.
- [ ] E2E: a scheduled check runs, fails on an induced outage, and alerts.
- [ ] FULL verify green.

## Phase completion criteria
F017-F018 `COMPLETE` with evidence; frontend sessions and synthetic checks are visible and
alert; phase smoke green.
