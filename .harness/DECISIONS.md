# DECISIONS — decision log

Indexes the architecture ADRs (`architecture/decisions/`) and records lighter decisions that
don't need a full ADR. Don't relitigate a decision here without a new one that supersedes it.

## Format
```
DEC-00N (<YYYY-MM-DD>): <decision, stated plainly>. — <why> [ADR-XXXX if applicable]
```

<!-- decisions go below -->
DEC-001 (2026-10-12): Air-gapped container registry mirror established locally (registry:2.8.3 on port 5001) with explicit manifests (`deploy/mirror/images.txt`, `deploy/mirror/setup-mirror.sh`). — Ensures strict air-gap compliance with zero public registry pulls at runtime.
DEC-002 (2026-10-12): OpenTelemetry Operator configured with built-in certificate auto-generation (`admissionWebhooks.autoGenerateCert.enabled=true`, `certManager.enabled=false`). — Eliminates external cert-manager dependency to keep ATO surface minimal.
DEC-003 (2026-10-12): Altinity ClickHouse Operator configured with native Helm 3 CRD management (`crdHook.enabled=false`). — Prevents unmirrored kubectl hook pods while ensuring reproducible CRD installation.
DEC-004 (2026-10-12): Prometheus Operator deployed via `kube-prometheus-stack` with non-operator components disabled for Phase 01 (`prometheusOperator.tls.enabled=false` when admission webhooks disabled). — Keeps strict scope boundary on operator baseline and minimizes initial footprint.
DEC-005 (2026-10-13): Grafana Beyla selected over Pixie as the eBPF network service floor for un-annotated services. — Single container binary (`localhost:5001/argus/beyla:2.2.4`), native OTLP HTTP export to Argus gateway, and minimal resource footprint (<256Mi RAM). [ADR-0005]
DEC-006 (2026-10-13): Parallel Execution Graph & Multi-Track Wave Architecture established across 5 Tracks (A-E) and 5 Waves with hard Synchronization Gates (G1-G5). — Eliminates single-thread bottleneck while guaranteeing zero port, CRD, or database schema conflicts during concurrent subagent execution. [PARALLEL_EXECUTION_GRAPH.md]
DEC-007 (2026-10-14): Grafana Pyroscope selected for continuous profiling (Feature F010). — Single-binary architecture (localhost:5001/argus/pyroscope:1.7.1), HTTP folded and pprof ingestion, FlameQL flame graph rendering, with anonymous usage reporting disabled for air-gap compliance. [ADR-0006]
DEC-008 (2026-10-15): Tiered Storage (Hot SSD -> Cold S3) and downsampling materialized views (raw -> 1m -> 1h) implemented in ClickHouse (Feature F014). — Prevents storage exhaustion and stabilizes query performance over long-term retention horizons.
DEC-009 (2026-10-15): SigNoz integrated Ruler & Alertmanager selected for threshold alerting and monitor lifecycle (Feature F011). — Standard PromQL evaluations directly against ClickHouse metrics with Alertmanager deduplication, flapping hysteresis, and Kubernetes PrometheusRule CRD compatibility. [ADR-0007]


