# ADR-0005: Selection of Grafana Beyla for eBPF Network Service Floor

- **Status**: Accepted
- **Date**: 2026-10-13
- **Author**: DevOps / Site Reliability Engineering

## Context
Project Argus requires an eBPF-based observability safety net (Feature F008) to discover and map network interactions for services that lack explicit OpenTelemetry SDK instrumentation or mutating webhook auto-instrumentation annotations.

The target environment is an air-gapped Kubernetes cluster (Docker Desktop / LinuxKit 7.0.12 arm64 and bare-metal Linux nodes). All telemetry must be ingested through the OpenTelemetry Collector gateway (`argus-gateway-collector`), sanitized for CJIS/PII compliance, and stored in ClickHouse for visualization in SigNoz APM.

## Decision
We select **Grafana Beyla** over Pixie (and Cilium Hubble) as the eBPF network instrumentation floor for Project Argus.

Beyla will be deployed as a Kubernetes DaemonSet (`deploy/ebpf/beyla.yaml`) in the `argus-system` namespace, utilizing granular Linux capabilities (`CAP_BPF`, `CAP_PERFMON`, `CAP_NET_ADMIN`, `CAP_SYS_PTRACE`, `CAP_SYS_RESOURCE`, `CAP_DAC_READ_SEARCH`) and exporting standard OTLP HTTP spans and metrics directly to `http://argus-gateway-collector.argus-system.svc.cluster.local:4318`.

## Consequences
- **Positive**:
  - **Single Go Binary**: Beyla requires only 1 container image (`localhost:5001/argus/beyla:2.2.4`), minimizing air-gapped mirror synchronization overhead and container attack surface.
  - **Native OpenTelemetry Spine**: Beyla pushes standard OTLP HTTP/Protobuf metrics and traces directly to the Argus gateway collector without intermediate proxies or proprietary query layers.
  - **Minimal Resource Footprint**: Memory consumption is bounded to 256 MiB per node and CPU is bounded to 200m, avoiding memory exhaustion on constrained nodes.
  - **Zero Code Modification**: Un-annotated microservices automatically appear on the SigNoz APM service catalog and dependency graph with RED (Rate, Errors, Duration) metrics.
- **Negative / Constraints**:
  - The node kernel must support BPF Type Format (BTF) and perf events (Linux 5.8+).
  - Requires `hostPID: true` to inspect `/proc` and discover containerized socket descriptors across namespaces.
  - Nodes lacking modern eBPF/BTF support will not generate eBPF traces and must degrade gracefully.

## Alternatives Considered
- **Pixie (New Relic / CNCF)**: Rejected due to heavy operational architecture (requires 6-8 microservice containers including Vizier PEM, Kelvin aggregator, metadata store, and NATS message broker), high per-node memory overhead (1-2 GiB RAM), and non-native OTLP export requiring proprietary PxL translation.
- **Cilium Hubble**: Rejected because it requires replacing the Kubernetes CNI with Cilium, which violates non-disruptive observability integration requirements for pre-existing clusters.
