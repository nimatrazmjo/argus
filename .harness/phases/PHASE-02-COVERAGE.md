# Phase 02 — Coverage

Make the platform see everything with minimal per-app effort, and make onboarding a new
service a one-line change. Depends on a green Phase 01 spine.
Execution architecture is governed by [`.harness/PARALLEL_EXECUTION_GRAPH.md`](file:///Users/nimatullahrazmjo/workstation/argus/.harness/PARALLEL_EXECUTION_GRAPH.md).

---

## F006 — SigNoz UI over ClickHouse
- **Execution Mode**: `[SEQUENTIAL GATE]` (Wave 1 UI Foundation)
- **Track**: Spine
- **Must wait for**: F005 (Phase 01 Spine verified)
- **Can run in parallel with**: None
- **Blocks**: F007, F008, F009, F010, F011
- **Status**: COMPLETE

### Acceptance criteria
- [x] SigNoz deployed (air-gapped images), reading the Phase 01 ClickHouse, showing APM, logs, traces, and dashboards for the sample service.
- [x] Usage telemetry / phone-home disabled; verified no egress.
- [x] Edge cases: ClickHouse unavailable (UI degrades, no crash), empty-state, large trace.
- [x] E2E: user opens the service in the UI and sees its traces/logs/metrics.
- [x] FULL verify green.

### Evidence expected
UI screenshots/paths under `.harness/evidence/F006/`; egress check output.

---

## F007 — Zero-code auto-instrumentation + onboarding runbook
- **Execution Mode**: `[PARALLEL TRACK A]` (Signal Expansion)
- **Track**: Track A (Metric & Signal Expansion)
- **Wave**: Wave 1
- **Must wait for**: F006
- **Can run in parallel with**: F008
- **Blocks**: F020 (topology context)
- **Status**: COMPLETE

### Acceptance criteria
- [x] An `Instrumentation` CR is configured so a single pod annotation injects the OTel auto-agent (at least one language end to end, e.g. python/java/node).
- [x] Onboarding a new service = add one annotation + redeploy; the service appears in the UI with traces and k8s metadata, no code change.
- [x] A runbook for app teams documents the one-line step.
- [x] Edge cases: unsupported language (fails gracefully, documented), annotation typo, sidecar resource limits.
- [x] E2E: annotate a fresh sample app -> it appears in the UI.
- [x] FULL verify green.

### Evidence expected
Before/after of the annotated workload; the runbook; e2e onboarding test under `.harness/evidence/F007/`.

---

## F008 — eBPF safety net (service map floor)
- **Execution Mode**: `[PARALLEL TRACK A]` (Signal Expansion)
- **Track**: Track A (Metric & Signal Expansion)
- **Wave**: Wave 1
- **Must wait for**: F006
- **Can run in parallel with**: F007
- **Blocks**: Gate G1 synchronization
- **Status**: COMPLETE

### Acceptance criteria
- [x] Beyla or Pixie deployed; un-annotated services still appear on a network-level service map.
- [x] Decision (Beyla vs Pixie) recorded as an ADR (`docs/decisions/ADR-0005-ebpf-safety-net-beyla.md`).
- [x] Edge cases: kernel/eBPF unsupported node (degrades), high-traffic service overhead bounded.
- [x] E2E: an un-annotated service shows up on the map.
- [x] FULL verify green.

### Evidence expected
Beyla DaemonSet manifests; ADR-0005; test scripts and evidence under `.harness/evidence/F008/`.

---

## F009 — Infra metrics
- **Execution Mode**: `[PARALLEL TRACK A]` (Signal Expansion — Wave 2 Active)
- **Track**: Track A (Metric & Signal Expansion)
- **Wave**: Wave 2
- **Must wait for**: F006, F008 (Sync Gate G1)
- **Can run in parallel with**: F010, F011, F014
- **Blocks**: F019 (Anomaly detection requires metric baselines), F021
- **Status**: COMPLETE

### Acceptance criteria
- [x] node-exporter + kube-state-metrics scraped into the store; node/pod/cluster metrics visible.
- [x] Air-gapped images mirrored to `localhost:5001/argus/*`.
- [x] Edge cases: node added/removed reflected, scrape target down.
- [x] E2E: `N/A — not user-facing` (asserted by a metrics-present check in ClickHouse/SigNoz).
- [x] FULL verify green.

### Evidence expected
Scrape manifests; `system.parts` / `signoz_metrics` query output showing node and pod metric series; edge case test transcript under `.harness/evidence/F009/`.

---

## F010 — Continuous profiling
- **Execution Mode**: `[PARALLEL TRACK A]` (Signal Expansion — Wave 2 Active)
- **Track**: Track A (Metric & Signal Expansion)
- **Wave**: Wave 2
- **Must wait for**: F006 (Sync Gate G1)
- **Can run in parallel with**: F009, F011, F014
- **Blocks**: None
- **Status**: NOT STARTED

### Acceptance criteria
- [ ] Pyroscope deployed; CPU/memory flame graphs for the sample service.
- [ ] Air-gapped images mirrored to `localhost:5001/argus/*`.
- [ ] Edge cases: profiling disabled per-service, overhead bounded.
- [ ] E2E: a flame graph renders for the sample service.
- [ ] FULL verify green.

### Evidence expected
Pyroscope deployment manifests; flame graph JSON/render export under `.harness/evidence/F010/`; overhead benchmarks.

---

## Phase completion & Wave Synchronization criteria
- **Wave 1 Gate (Gate G1)**: F006, F007, and F008 are `COMPLETE` with evidence. (PASSED)
- **Wave 2 Gate (Gate G2)**: F009 and F010 complete concurrently alongside F011 (Alerting) and F014 (Retention) with full verification green before unlocking Wave 3.
