# ADR-0007: Declarative Alerting, Threshold Monitors, and Alertmanager Deduplication

- **Status**: Accepted
- **Date**: 2026-10-15
- **Author**: SRE / Observability Platform Engineer

## Context
Project Argus requires a centralized threshold monitoring and alerting engine (Feature F011) capable of evaluating metric breaches, managing alert state transitions (inactive -> pending -> firing -> resolved), deduplicating notifications, and preventing flapping.

The platform must support declarative rule specifications (Kubernetes `PrometheusRule` CRD and SigNoz Ruler JSON manifests), provide integration with Alertmanager notification channels, and satisfy strict air-gap compliance with zero external egress.

## Decision
We implement **SigNoz Ruler & Prometheus Alertmanager Core** as the alerting and monitor evaluation engine for Project Argus, paired with declarative Kubernetes `PrometheusRule` Custom Resources.

Key implementation decisions:
1. **Unified Ruler & Alert Engine**: We leverage SigNoz's integrated Ruler service (`/api/v2/rules`) and Alertmanager (`/api/v1/alerts`, `/api/v1/channels`) running on port `8080` in the `argus-system` namespace. This evaluates PromQL metric expressions directly against the ClickHouse metrics storage tier (`signoz_metrics`).
2. **Declarative Rule Synchronization**: Alert manifests are authored declaratively in `deploy/alerting/rules.json` and synchronized via `deploy/alerting/apply-rules.sh`. In addition, Kubernetes-native CRD manifests are maintained in `deploy/alerting/prometheus-rules.yaml` (`monitoring.coreos.com/v1`).
3. **Flapping Prevention & Hysteresis**: Rules support configurable evaluation windows (`evalWindow: 2m0s`) and match conditions (`all_the_times` vs `at_least_once`), ensuring transient anomalies or sub-window spikes do not flap notifications.
4. **Deadman Absence Detection**: The engine supports inverted comparison rules (`op: below_or_equal`, `target: 0` on `count(...)` queries) to detect silent telemetry pipeline failure or collector disconnects.
5. **Alertmanager Deduplication**: Firing alerts are grouped and deduplicated by composite key (`alertname`, `service`) before dispatching to notification receivers (e.g. `argus-default-webhook`).
6. **Air-Gap Compliance**: Notification webhooks target cluster-internal services (e.g. `http://argus-sample-service.argus-system.svc.cluster.local:8080/api/alerts`), with external telemetry and SaaS alert dispatchers strictly isolated.

## Consequences
- **Positive**:
  - **Native Metric Correlation**: Alert rules use standard PromQL expressions evaluated directly against ingested infrastructure and APM metrics in ClickHouse.
  - **Zero Additional Daemons**: Eliminates the need to deploy standalone Prometheus server replicas solely for alerting, minimizing cluster memory overhead.
  - **Declarative GitOps Compatibility**: Rules can be deployed via CI/CD GitOps pipelines using JSON API sync or Kubernetes `PrometheusRule` CRDs.
  - **Deduplication by Default**: Alertmanager deduplication prevents alert floods across high-cardinality distributed microservices.
- **Negative / Constraints**:
  - Rule evaluation frequency should be tuned (10s–60s) to balance alert responsiveness against ClickHouse query load.
  - Complex custom notification templates require configuration within the SigNoz Alertmanager channel specifications.

## Alternatives Considered
- **Standalone Prometheus Server with Alertmanager**: Evaluated deploying a full Prometheus instance to scrape and evaluate alerts. Rejected due to redundant metric storage, duplication of ClickHouse ingestion, and unnecessary resource footprint.
- **Grafana Alerting**: Rejected due to additional complex database requirements and lack of native zero-copy integration with the SigNoz APM telemetry spine.
