# ADR-0011: Synthetic Canary Probing, Browser Checks & Prober Metrics Pipeline

## Status
Accepted

## Context
Production monitoring requires proactive detection of user-facing service disruptions before real users encounter errors (Feature F018). While APM (F006) and tracing (F004) inspect live user traffic, dormant paths, degraded authentication endpoints, or complete ingress failures may produce zero telemetry.

In air-gapped federal environments:
1. External SaaS synthetic probers (Datadog Synthetics, Pingdom) cannot reach private internal clusters.
2. Synthetic probers must execute inside Kubernetes with strict air-gap compliance.
3. Probes must support multi-step transaction workflows (HTTP/API status, latency SLA, header-authenticated checks, and page content assertions).
4. Probe failure events must seamlessly feed the centralized Alertmanager (F011) and ServiceNow incident paging (F013) path.

## Decision
1. **Synthetic Canary Prober (`argus-synthetic-prober`)**:
   - Deploy `argus-synthetic-prober` as a scheduled prober daemon and Kubernetes CronJob runner.
   - Run in `argus-system` using mirrored `localhost:5001/argus/python:3.12-alpine`.
   - Execute configured probe definitions:
     - Availability check (`sample-service-api` -> `http://argus-sample-service:8080/order`).
     - Multi-step transaction workflow (`sample-service-slo-dashboard` -> `/slo` content verification).
     - Authenticated / auth-walled verification (`secure-endpoint-probe` -> headers and token assertion).
2. **Prometheus Metrics Exporter**:
   - The prober serves standard Prometheus metrics on `:9115/metrics`:
     - `argus_synthetic_probe_success{target, probe_type}`: Gauge (1 for healthy, 0 for failure).
     - `argus_synthetic_probe_duration_seconds{target, probe_type}`: Histogram & Gauge of execution latency.
     - `argus_synthetic_probe_step_duration_seconds{target, step}`: Multi-step transaction breakdown.
   - Scraped continuously by OTel collectors and ingested into ClickHouse `default.otel_metrics_gauge`.
3. **Alerting & Incident Integration**:
   - Declarative alert rules in `deploy/synthetics/synthetic-rules.json`:
     - `ArgusSyntheticProbeFailure`: fires when `argus_synthetic_probe_success == 0`.
     - `ArgusSyntheticProbeLatencyDegraded`: fires when probe duration > 1.5s.
   - When a probe breaches, SigNoz Ruler fires an alert routed through Paging Gateway (F013) to ServiceNow.

## Consequences
- **Positive**:
  - Proactive outage detection 24/7 independently of organic traffic.
  - Native Prometheus metrics scraped into ClickHouse for unified dashboarding.
  - Automatic incident ticket creation in ServiceNow upon probe failure.
- **Negative / Trade-offs**:
  - Requires maintaining scheduled prober definitions alongside application deployments.
