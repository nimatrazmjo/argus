# Phase 02 — Coverage

Make the platform see everything with minimal per-app effort, and make onboarding a new
service a one-line change. Depends on a green Phase 01 spine.

## F006 — SigNoz UI over ClickHouse
**Status**: NOT STARTED
### Acceptance criteria
- [ ] SigNoz deployed (air-gapped images), reading the Phase 01 ClickHouse, showing APM, logs, traces, and dashboards for the sample service.
- [ ] Usage telemetry / phone-home disabled; verified no egress.
- [ ] Edge cases: ClickHouse unavailable (UI degrades, no crash), empty-state, large trace.
- [ ] E2E: user opens the service in the UI and sees its traces/logs/metrics.
- [ ] FULL verify green.
### Evidence expected
UI screenshots/paths under `.harness/evidence/F006/`; egress check output.

## F007 — Zero-code auto-instrumentation + onboarding runbook
**Status**: NOT STARTED
### Acceptance criteria
- [ ] An `Instrumentation` CR is configured so a single pod annotation injects the OTel auto-agent (at least one language end to end, e.g. python/java/node).
- [ ] Onboarding a new service = add one annotation + redeploy; the service appears in the UI with traces and k8s metadata, no code change.
- [ ] A runbook for app teams documents the one-line step.
- [ ] Edge cases: unsupported language (fails gracefully, documented), annotation typo, sidecar resource limits.
- [ ] E2E: annotate a fresh sample app -> it appears in the UI.
- [ ] FULL verify green.
### Evidence expected
Before/after of the annotated workload; the runbook; e2e onboarding test.

## F008 — eBPF safety net (service map floor)
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Beyla or Pixie deployed; un-annotated services still appear on a network-level service map.
- [ ] Decision (Beyla vs Pixie) recorded as an ADR.
- [ ] Edge cases: kernel/eBPF unsupported node (degrades), high-traffic service overhead bounded.
- [ ] E2E: an un-annotated service shows up on the map.
- [ ] FULL verify green.

## F009 — Infra metrics
**Status**: NOT STARTED
### Acceptance criteria
- [ ] node-exporter + kube-state-metrics scraped into the store; node/pod/cluster metrics visible.
- [ ] Edge cases: node added/removed reflected, scrape target down.
- [ ] E2E: `N/A — not user-facing` (asserted by a metrics-present check).
- [ ] FULL verify green.

## F010 — Continuous profiling
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Pyroscope deployed; CPU/memory flame graphs for the sample service.
- [ ] Edge cases: profiling disabled per-service, overhead bounded.
- [ ] E2E: a flame graph renders for the sample service.
- [ ] FULL verify green.

## Phase completion criteria
F006-F010 all `COMPLETE` with evidence; a new service can be onboarded with one annotation and
is fully visible; phase smoke green.
