# Sprint Contract — F008: eBPF Safety Net (Service Map Floor)

Feature: F008 — eBPF safety net (Beyla): network-level service map for un-annotated services
Phase: Phase 02 — Coverage
Date: 2026-10-13

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] **Architecture Decision Record (ADR-0005)**:
  - Document evaluation of Grafana Beyla vs. Pixie.
  - Record decision to adopt Grafana Beyla for low footprint, native OTLP export, and air-gapped simplicity.
  - Documented in `docs/decisions/ADR-0005-ebpf-safety-net-beyla.md` and `.harness/DECISIONS.md`.
- [x] **Air-Gapped Mirroring of Grafana Beyla**:
  - Image `grafana/beyla:2.2.4` mirrored to `localhost:5001/argus/beyla:2.2.4`.
  - Added to `deploy/mirror/images.txt`.
- [x] **Declarative eBPF DaemonSet Deployment (`deploy/ebpf/beyla.yaml`)**:
  - ServiceAccount, ClusterRole, and ClusterRoleBinding for Kubernetes metadata discovery.
  - ConfigMap with discovery rules targeting HTTP/TCP open ports (80, 443, 8000-9999), excluding kube-system.
  - DaemonSet with `hostPID: true`, bounded capabilities (`BPF`, `PERFMON`, `NET_ADMIN`, `SYS_PTRACE`, `SYS_RESOURCE`, `DAC_READ_SEARCH`), and mounts for `/sys/fs/cgroup`, `/sys/kernel/debug`, `/sys/kernel/tracing`.
  - OTLP traces and metrics sink pointed to `http://argus-gateway-collector.argus-system.svc.cluster.local:4318`.
- [x] **End-to-End Service Map Floor Verification (`scripts/test-ebpf.sh`)**:
  - Deploy completely un-annotated microservice (`argus-unannotated-service`) with zero OTel SDK imports and zero pod annotations.
  - Assert pod has 0 init containers and 0 OTel env vars.
  - Generate synthetic HTTP transactions against the un-annotated service.
  - eBPF probe captures kernel socket traffic and exports OTLP spans/flow metrics to `argus-gateway-collector`.
  - Gateway passes spans through redaction processor into ClickHouse (`signoz_traces.signoz_index_v3` / `signoz_metrics.samples_v4`).
  - Verify un-annotated service appears in SigNoz APM service catalog (`/api/v1/services/list`) and dependency map.
- [x] **Edge Cases & Failure Paths (`scripts/test-ebpf-edge-cases.sh`)**:
  - **Graceful degradation on unsupported node**: Beyla degrades gracefully without capabilities, never panicking the host kernel.
  - **High-traffic service overhead bounded**: DaemonSet enforces strict CPU (200m) and memory (256Mi) limits.
  - **Dynamic pod lifecycle**: Beyla handles dynamic pod creation/deletion without crash looping.
  - **Collector partition / outage resilience**: Asynchronous ring buffer drops telemetry under collector outage without blocking app sockets.
  - **Air-gap compliance**: Verified 0 external egress connections from Beyla daemon.
- [x] **Regression Suite**:
  - Full `./scripts/verify.sh` passes cleanly (17/17 steps).

## 2. Edge Cases & Failure Paths (from `verification/edge-cases.md`)
- **Kernel / eBPF Capabilities Unavailable**:
  - Pod without BPF capabilities logs an error and exits cleanly without destabilizing host kernel or other containers.
- **Resource Constraints**:
  - DaemonSet memory bound to 256Mi, CPU bound to 200m to prevent node memory exhaustion.
- **Collector Outage**:
  - Non-blocking ring buffer in kernel ensures applications experience zero latency degradation if the collector fails.

## 3. E2E Scenario
1. Deploy `deploy/ebpf/beyla.yaml` to `argus-system`.
2. Deploy raw un-instrumented test workload `argus-unannotated-service` (no annotations, no SDKs).
3. Send HTTP traffic from `argus-sample-service` to `argus-unannotated-service:8085/healthz`.
4. Verify Beyla kernel probes synthesize OTLP spans/flow metrics.
5. Verify metrics/spans land in ClickHouse `signoz_metrics.samples_v4` / `signoz_traces.signoz_index_v3`.
6. Verify service catalog is queried in SigNoz APM catalog (`/api/v1/services/list`).
7. Clean up test workload and collect evidence in `.harness/evidence/F008/`.
