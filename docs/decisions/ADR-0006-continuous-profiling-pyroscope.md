# ADR-0006: Selection of Grafana Pyroscope for Continuous Profiling

- **Status**: Accepted
- **Date**: 2026-10-14
- **Author**: Profiling Engineer / SRE

## Context
Project Argus requires a continuous profiling solution (Feature F010) to collect, store, and analyze execution profiles (CPU and memory allocation flame graphs) across microservices deployed in an air-gapped Kubernetes cluster.

Continuous profiling complements metrics, traces, and logs by providing line-level visibility into CPU consumption, memory allocation churn, and resource bottlenecks without requiring manual profiler attaches or heavy tracing overhead.

All components in Project Argus operate under strict air-gap compliance (zero public registry pulls at runtime, zero phone-home telemetry or egress, and bounded CPU/memory footprints on resource-constrained nodes).

## Decision
We select **Grafana Pyroscope** (`grafana/pyroscope:1.7.1`) in single-binary monolithic mode with local PersistentVolume storage as the continuous profiling engine for Project Argus.

Key implementation decisions:
1. **Air-Gapped Deployment & Provenance**: The container image is mirrored to `localhost:5001/argus/pyroscope:1.7.1` and deployed as a bounded single-pod Deployment with a dedicated 1 GiB PersistentVolumeClaim (`pyroscope-data`) in the `argus-system` namespace.
2. **Strict Telemetry & Egress Prohibition**: Pyroscope is launched with `-usage-stats.enabled=false` to permanently disable anonymous usage reporting, verifying zero external network egress in accordance with DHS ATO standards.
3. **Ingestion & Flame Graph Query API**: The Pyroscope server listens on port `4040` (`pyroscope.argus-system.svc.cluster.local:4040`), exposing:
   - `POST /ingest`: High-throughput ingestion supporting folded/collapsed stack frames and standard Google `pprof` protobuf formats.
   - `GET /pyroscope/render`: Queryable FlameQL API returning flamebearer JSON hierarchy (`levels`, `names`, `numTicks`, `timeline`) for CPU (`process_cpu:cpu:nanoseconds:cpu:nanoseconds`) and memory (`memory:alloc_space:bytes::` or `alloc_objects`).
   - `GET /ready`: Standard Kubernetes readiness and liveness probe endpoint.
4. **Microservice Profiling Integration**: Workloads (e.g., `argus-sample-service`) emit folded stack traces periodically via HTTP to the internal cluster endpoint. Profiling is toggled via environment variables (`PROFILING_ENABLED=true/false`) with non-blocking error handling to ensure application availability during collector maintenance.

## Consequences
- **Positive**:
  - **Single Static Go Binary**: No external database dependencies (e.g., PostgreSQL or MinIO required for minimal footprint); stores directly to local PersistentVolume blocks.
  - **High Performance / Low Overhead**: Flamebearer tree format allows rendering full flame graphs with sub-millisecond query latencies and <256Mi RAM server usage.
  - **Multi-Language Support**: Supports Python, Go, Java, Node.js, and eBPF profiling profiles.
  - **Native Air-Gap Compliance**: Complete functionality offline with usage reporting explicitly disabled.
- **Negative / Constraints**:
  - Single-binary local storage mode is bound to a single read-write volume (sufficient for cluster-internal continuous profiling retention).
  - Workloads must have network connectivity to port 4040 within `argus-system`.

## Alternatives Considered
- **Parca (Polar Signals)**: Evaluated Parca server and Parca agent. Rejected due to complex eBPF kernel requirements across non-BTF nodes, larger memory footprint (>1 GiB), and lack of native support for folded stack HTTP ingestion for standard lightweight microservice runtimes.
- **Pixie CPU Profiler**: Rejected in ADR-0005 due to heavy cluster operator overhead (Vizier, Kelvin, NATS) and lack of persistent historical flame graph querying.
