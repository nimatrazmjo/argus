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
