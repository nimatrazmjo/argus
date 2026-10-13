# Sprint Contract — F007: Zero-Code Auto-Instrumentation & Service Onboarding

Feature: F007 — Zero-code auto-instrumentation via OTel Operator annotation; onboarding runbook for app teams
Phase: Phase 02 — Coverage
Date: 2026-10-12

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] **Instrumentation CR configured** (`deploy/otel/instrumentation.yaml`):
  - Uses air-gapped mirrored images from `localhost:5001/argus/*`:
    - Python: `localhost:5001/argus/autoinstrumentation-python:0.65b0`
    - Node.js: `localhost:5001/argus/autoinstrumentation-nodejs:0.78.0`
    - Java: `localhost:5001/argus/autoinstrumentation-java:2`
  - Targets the Argus OTel Gateway at `http://argus-gateway-collector.argus-system.svc.cluster.local:4318`.
  - Configures propagators (`tracecontext`, `baggage`, `b3`) and sampler (`parentbased_always_on`).
  - Sets safe init-container resource limits (e.g. 100m CPU, 128Mi RAM).
  - Injects k8s resource attributes (`k8s.pod.name`, `k8s.namespace.name`, `k8s.node.name`).
- [x] **Zero-Code Onboarding via Pod Annotation**:
  - Adding `instrumentation.opentelemetry.io/inject-python: "true"` (or `inject-nodejs: "true"`, `inject-java: "true"`) injects the auto-agent without modifying application code or Dockerfile.
  - Pod starts successfully, mounts the agent bundle, and sends OTLP spans directly to the gateway.
  - Telemetry passes through the gateway redaction processor and lands in ClickHouse & SigNoz.
- [x] **Onboarding Runbook** (`docs/runbooks/service-onboarding.md`):
  - Plain English, 1-line copy-paste onboarding instructions for DHS application developers.
  - Covers Python, Node.js, and Java workloads.
  - Explains verification via SigNoz UI / API, troubleshooting tips, and air-gapped configuration.
- [x] **Edge Cases & Failure Paths** (`scripts/test-auto-instrumentation-edge-cases.sh`):
  - **Unsupported language**: Unrecognized annotation fails gracefully without pod disruption.
  - **Annotation typo / invalid target**: Typo does not crash the admission controller or affect unaffected pods.
  - **Init container resource constraints**: Resource bounds verified; pod stays within quota.
  - **OTel Gateway unavailable**: Workload continues serving HTTP requests without crashing when collector endpoint is degraded.
- [x] **E2E Integration** (`scripts/test-auto-instrumentation.sh`):
  - Deploy a completely un-instrumented Python service (zero OTel imports, standard Python HTTP server).
  - Assert baseline has no init-containers or OTel env vars.
  - Apply auto-instrumentation annotation.
  - Mutating webhook injects `opentelemetry-auto-instrumentation-python`.
  - Generate HTTP traffic against the service.
  - Verify spans land in ClickHouse (`signoz_traces.signoz_index_v3`) with k8s metadata and correct service name.
  - Verify service appears in SigNoz `/api/v1/services`.
- [x] **Air-Gap Strictness**:
  - 100% of images resolve from `localhost:5001/argus/*`.
- [x] **Regression Suite**:
  - All steps in `./scripts/verify.sh` pass cleanly.

## 2. Edge Cases & Failure Paths (from `verification/edge-cases.md`)
- **Mutating Webhook Resilience**:
  - Webhook failures must not take down the entire cluster. `failurePolicy: Ignore` on pod mutation webhook ensures apps can still launch even if the operator is temporarily down.
- **Resource Constraints**:
  - Init containers have CPU requests/limits to prevent memory exhaustion on resource-constrained worker nodes.
- **Collector Endpoint Down**:
  - OTel auto-instrumentation SDKs drop spans asynchronously without blocking HTTP request execution if collector is unavailable.

## 3. E2E Scenario
1. Deploy `Instrumentation` CR in `argus-system`.
2. Deploy a zero-code test application (`argus-auto-service`) containing no OpenTelemetry libraries.
3. Annotate the deployment with `instrumentation.opentelemetry.io/inject-python: "true"`.
4. Kubernetes mutating webhook injects the auto-agent init container and sets `PYTHONPATH` / `OTEL_*` env vars.
5. Service pod becomes `Ready` (1/1).
6. Send synthetic HTTP requests (`curl http://<service-ip>:8080/auto-test`).
7. Verify spans are queryable in ClickHouse and service is listed in SigNoz UI / API.
8. Capture verification evidence in `.harness/evidence/F007/`.

## 4. Plan (thinnest vertical slice)
1. Mirror latest auto-instrumentation images (`python:0.65b0`, `nodejs:0.78.0`, `java:2`) to `localhost:5001/argus/*` and update `deploy/mirror/images.txt`. (Done)
2. Create `deploy/otel/instrumentation.yaml` with the `Instrumentation` custom resource.
3. Apply `deploy/otel/instrumentation.yaml` in `argus-system`.
4. Create sample un-instrumented app manifest `deploy/sample-app/auto-instrumented-service.yaml`.
5. Create comprehensive runbook `docs/runbooks/service-onboarding.md`.
6. Write functional test `scripts/test-auto-instrumentation.sh`.
7. Write edge case test `scripts/test-auto-instrumentation-edge-cases.sh`.
8. Integrate into `scripts/verify.sh`.
9. Execute full test suite, collect evidence, update harness docs, and commit.
