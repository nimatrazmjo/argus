# Phase 01 — Foundation

Prove the observability spine works end to end, inside Kubernetes, air-gapped, with
compliance on. Nothing in later phases starts until every feature here is COMPLETE with
evidence and the phase smoke test is green. Every image/chart is pulled from the internal
mirror, not a public registry.

## F001 — Cluster baseline + operators
**Status**: IN PROGRESS

### Acceptance criteria
- [ ] OpenTelemetry Operator, a ClickHouse operator (Altinity), and the Prometheus Operator are installed via Helm into a dedicated namespace, all images resolved from the internal mirror (no public-registry pulls).
- [ ] `scripts/init.sh` exists and runs green: validates cluster access, required CRDs present, operators Ready.
- [ ] `scripts/check-architecture.sh` exists (no-op exit 0 until `rules/layer-boundaries.md` is filled).
- [ ] Install is declarative (Helm values / GitOps), re-appliable without manual steps.
- [ ] Edge/error cases from `verification/edge-cases.md` (applicable: missing CRD, mirror unreachable, partial operator rollout) covered.
- [ ] E2E: `N/A — not user-facing` (operator install asserted by init smoke).
- [ ] Boundary invariants: obeys `rules/layer-boundaries.md` (no-op until filled).
- [ ] FULL verify passes, no regressions.

### Evidence expected
`init.sh` output showing operators Ready; `helm list`; `kubectl get crd` for each operator; proof images came from the mirror.

## F002 — ClickHouse HA + object-storage tier
**Status**: NOT STARTED

### Acceptance criteria
- [ ] ClickHouse runs HA (2 shards/replicas appropriate to a 10-50 app load) via the operator.
- [ ] A storage policy tiers cold parts to S3/MinIO; verified a part moves to object storage.
- [ ] Survives a pod restart with no data loss (insert -> kill pod -> query returns the row).
- [ ] Edge cases: disk-pressure, replica down, object-store unreachable (writes still land locally).
- [ ] E2E: `N/A — not user-facing`.
- [ ] FULL verify green.

### Evidence expected
Insert/kill/query transcript; `system.parts` showing a part on the S3 disk; replica status.

## F003 — OTel Collector pipeline (ingest spine)
**Status**: NOT STARTED

### Acceptance criteria
- [ ] Node-level DaemonSet (kubelet/cAdvisor scrape, pod-log filelog receiver, OTLP receiver) + a gateway Deployment (batch, k8sattributes enrichment) deployed.
- [ ] OTLP metrics, logs, and traces written to ClickHouse via the gateway.
- [ ] Every record carries k8s resource attributes (namespace, pod, node) from the k8sattributes processor.
- [ ] Gateway batches and applies resource detection; config is one source of truth, not per-app.
- [ ] Edge cases: collector restart (no crash loop), malformed OTLP rejected cleanly, backpressure when ClickHouse is slow.
- [ ] E2E: `N/A` here — correlation is proven in F004.
- [ ] FULL verify green.

### Evidence expected
A test OTLP export landing as rows in each ClickHouse table, with k8s attributes populated.

## F004 — End-to-end correlation proof
**Status**: NOT STARTED

### Acceptance criteria
- [ ] A sample instrumented service emits a metric, a trace, and a log for one request.
- [ ] All three are queryable and correlate by the same trace id in SigNoz (or via ClickHouse query pre-UI).
- [ ] An automated e2e test drives the request and asserts the correlated trio exists.
- [ ] Edge cases: dropped span, log without trace id (degrades, does not break), clock skew.
- [ ] E2E: primary flow (request -> metric+trace+log correlated) passes end to end.
- [ ] FULL verify green.

### Evidence expected
e2e test id + output; a query showing metric, trace, and log joined on trace id.

## F005 — PII/CJIS redaction at ingest
**Status**: NOT STARTED

### Acceptance criteria
- [ ] A redaction/transform processor in the collector pipeline strips/masks the agreed sensitive fields (configurable list) before the exporter.
- [ ] A test proves a sensitive field present in the OTLP input is absent from ClickHouse storage.
- [ ] Redaction runs on logs, trace attributes, and span events.
- [ ] Config is reviewable by the compliance persona (readable field list, not opaque regex soup where avoidable).
- [ ] Edge cases: nested attributes, field in a log body vs attribute, redaction failure must drop not leak.
- [ ] E2E: redaction asserted as part of the F004 flow with sensitive fields injected.
- [ ] FULL verify green.

### Evidence expected
Input-with-PII -> stored-without-PII transcript; the processor config; the assertion test.

## Phase completion criteria
Every feature F001-F005 is `COMPLETE` with evidence, and the phase smoke test (init green +
one request producing a correlated, redacted metric+trace+log) passes, before Phase 02 starts.
