# Sprint Contract — F001: Cluster baseline + operators

Feature: F001 — Cluster baseline + operators
Phase: Phase 01 — Foundation
Date: 2026-10-12

> Filled by the Planner/Maker before building. All acceptance criteria map to concrete, reproducible checks.

## 1. Scope & Acceptance Criteria
- [ ] OpenTelemetry Operator, Altinity ClickHouse operator, and Prometheus Operator installed via Helm into dedicated namespace (`argus-system`), with all images resolved strictly from the internal mirror (no public-registry pulls).
  - *Evidence*: `helm list -n argus-system`, and `kubectl get pods -n argus-system -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{range .spec.containers[*]}{.image}{" "}{end}{"\n"}{end}'` proving all container images originate from the internal mirror.
- [ ] `scripts/init.sh` exists and runs green:
  - Validates cluster connectivity and Kubernetes version.
  - Validates dedicated namespace `argus-system`.
  - Validates required CRDs:
    - OTel: `opentelemetrycollectors.opentelemetry.io`, `instrumentations.opentelemetry.io`
    - Altinity: `clickhouseinstallations.clickhouse.altinity.com`
    - Prometheus: `prometheuses.monitoring.coreos.com`, `prometheusrules.monitoring.coreos.com`, `servicemonitors.monitoring.coreos.com`, `podmonitors.monitoring.coreos.com`
  - Validates operator Deployments are in `Ready` condition.
  - Validates image origin audit passes (no unmirrored images).
  - *Evidence*: `./scripts/init.sh` exits 0 with structured summary.
- [ ] `scripts/check-architecture.sh` exists:
  - Implements architecture boundary enforcement (permissive no-op exit 0 until `rules/layer-boundaries.md` is populated).
  - *Evidence*: `./scripts/check-architecture.sh` exits 0.
- [ ] Install is declarative (Helm values / GitOps), re-appliable idempotently without manual steps:
  - `deploy/helm/values/` contains declarative values for each operator with explicit mirror configuration.
  - `scripts/deploy-operators.sh` applies the configuration idempotently.
  - *Evidence*: Running deploy twice produces clean idempotent upgrade/no-op with exit 0.
- [ ] Edge/error cases from `verification/edge-cases.md` covered:
  - Missing CRD detection.
  - Internal mirror unreachable / image pull failure detection.
  - Degraded / partial operator rollout detection.
  - *Evidence*: Automated test script `./scripts/test-edge-cases.sh` asserts each failure condition is caught with descriptive error.
- [ ] Boundary invariants: obeys `rules/layer-boundaries.md` (check-architecture passes).
- [ ] E2E: `N/A — not user-facing` (operator foundation asserted by init smoke & CRD readiness).
- [ ] No regressions: the FULL verify (`./scripts/verify.sh`) passes with zero errors.

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
- **State / missing dependency**: Missing CRD -> `init.sh` and edge-case tests detect missing CRDs and return non-zero with explicit names of missing CRDs.
- **Failure / resilience**: Mirror unreachable -> simulated unreachable mirror endpoint is detected; deployment/health check fails fast with mirror connection error instead of hanging indefinitely.
- **State / partial failure**: Partial operator rollout / CrashLoopBackOff -> `init.sh` checks pod readiness and rollout status; fails with timeout/unready details if an operator pod fails to reach Ready.
- **Idempotency**: Running `deploy-operators.sh` consecutively does not duplicate resources or fail on existing namespaces/CRDs.
- **N/A categories**:
  - Input/data (user forms, unicode): N/A for Kubernetes operator deployment.
  - Concurrency (user race condition): N/A for infrastructure baseline.
  - UI: N/A for operator baseline.

## 3. E2E scenario(s)
`N/A — not user-facing` (operator infrastructure baseline; verified by automated smoke check in `init.sh` asserting operator controller loops respond to CRD creations).

## 4. Plan (thinnest vertical slice)
1. Search and pin the latest verified Docker images and Helm charts for senior DevOps standards:
   - OpenTelemetry Operator: `0.160.0` (Chart `0.124.1`)
   - Altinity ClickHouse Operator: `0.27.4` (Chart `0.27.4`)
   - Prometheus Operator: `v0.94.1` (Chart `92.3.0`)
   - Docker Registry mirror: `registry:2.8.3`
2. Create `deploy/mirror/` setup script and image manifest to establish the internal mirror registry (`localhost:5001` / cluster-accessible mirror) and mirror all required images.
3. Create declarative Helm values under `deploy/helm/values/`:
   - `opentelemetry-operator-values.yaml`: mirror repository configured, webhook cert auto-generation enabled.
   - `clickhouse-operator-values.yaml`: mirror repository configured for operator and metrics exporter.
   - `kube-prometheus-stack-values.yaml`: mirror repository configured for prometheus-operator and config-reloader, non-operator components disabled for minimal ATO footprint.
4. Create `scripts/deploy-operators.sh` to declaratively deploy the operators to namespace `argus-system`.
5. Create `scripts/check-architecture.sh` enforcing layer boundaries (no-op exit 0 until rules filled).
6. Create `scripts/init.sh` validating cluster access, CRDs, operator readiness, and mirror image origin.
7. Create `scripts/test-edge-cases.sh` covering missing CRD, unreachable mirror, and degraded rollout.
8. Create `scripts/verify.sh` running full verification suite.
9. Verify all acceptance criteria, record evidence in `CHANGELOG.md`, update tracking files.

## 5. Out of scope (parked, not built)
- ClickHouse cluster instance deployment (F002).
- OTel Collector pipelines and agents (F003).
- End-to-end tracing/metrics/logging correlation app (F004).
- PII redaction processors (F005).

## 6. New dependencies (with justification)
- `helm` (already present on system): standard declarative package manager for Kubernetes operators.
- `docker registry:2.8.3`: standard local/internal OCI registry for air-gapped image mirroring.
- `open-telemetry/opentelemetry-operator`: official operator for OpenTelemetry collectors and instrumentations.
- `clickhouse-operator/altinity-clickhouse-operator`: official Altinity operator for ClickHouse clusters.
- `prometheus-community/kube-prometheus-stack`: official Prometheus operator for monitoring CRDs and scraping.

## 7. Risks
- OpenTelemetry operator webhook cert generation: Handled by setting `admissionWebhooks.autoGenerateCert.enabled=true` and `admissionWebhooks.certManager.enabled=false` to avoid requiring external cert-manager.
- Image resolution in Docker Desktop: Docker Desktop natively supports insecure registries on `localhost:5001` or through an in-cluster mirror service.
