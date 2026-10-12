# CURRENT TASK

**Feature**: F003 — OTel Collector pipeline (ingest spine)
**Phase**: Phase 01 — Foundation
**Status**: IN PROGRESS

## Exact next step
1. Write `verification/sprint-contract.md` for F003, mapping each acceptance item in
   `phases/PHASE-01-FOUNDATION.md` to a concrete check.
2. Check OTel Collector image (`localhost:5001/argus/opentelemetry-collector-k8s:0.160.0` or contrib with ClickHouse exporter).
3. Create declarative OpenTelemetryCollector custom resources for node DaemonSet (cAdvisor/kubelet, filelog, OTLP receiver) and gateway Deployment (batch, k8sattributes processor, ClickHouse exporter).
4. Verify OTLP metrics, logs, and traces flow from collector to ClickHouse with k8s resource attributes.
5. Implement automated edge cases test battery for collector backpressure, crash loops, and malformed inputs.

## Acceptance (summary)
See `phases/PHASE-01-FOUNDATION.md` -> F003 for full criteria and the signed
`verification/sprint-contract.md` for this feature.

## Definition of done
Every acceptance item met + evidence in `CHANGELOG.md` + Evaluator PASS + check-architecture
clean + PR reviewed clean (inert until a remote + gh exist). See `AGENTS.md`.
