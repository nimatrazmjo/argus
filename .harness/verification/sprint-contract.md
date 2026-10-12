# Sprint Contract — F006: SigNoz UI over ClickHouse

Feature: F006 — SigNoz UI over ClickHouse
Phase: Phase 02 — Coverage
Date: 2026-10-12

> Filled before building. Maps every acceptance criterion to concrete, reproducible verification checks.

## 1. Scope & Acceptance Criteria
- [x] SigNoz deployed (air-gapped images from `localhost:5001/argus/*`), reading the Phase 01 ClickHouse HA cluster.
  - Manifests located in `deploy/signoz/`.
  - SigNoz web frontend and query-service reachable on port 8080 (ClusterIP / port-forward).
  - Telemetry store / schema migrations applied against ClickHouse HA.
- [x] Telemetry store integration:
  - SigNoz connected to `clickhouse-argus-clickhouse:9000` (user `default`, password `argus123`).
  - Redacted telemetry from OpenTelemetry gateway is fed into SigNoz ClickHouse storage.
  - SigNoz shows APM, logs, traces, and service map for `argus-sample-service`.
- [x] Usage telemetry / phone-home disabled:
  - Phone-home, analytics, and telemetry explicitly disabled via environment configuration (`TELEMETRY_ENABLED=false`, `SIGNOZ_TELEMETRY=false`, `REPORT_USAGE=false`).
  - Verified no outbound egress traffic to public internet / analytics endpoints.
- [x] Edge cases covered (`scripts/test-signoz-edge-cases.sh`):
  - **ClickHouse unavailable**: When ClickHouse connection is temporarily interrupted, SigNoz UI/API degrades gracefully (returns error / degraded status, pod does not crash loop or lose state).
  - **Empty-state handling**: Services / queries with no telemetry return clean empty responses without unhandled 500 exceptions or UI crashes.
  - **Large trace handling**: Spans with large payloads or deep call stacks query and render within SLA without memory exhaustion or timeouts.
- [x] E2E integration:
  - User / client queries SigNoz API / UI:
    - Service list endpoint `/api/v1/services` returns `argus-sample-service`.
    - Traces query returns traces for `argus-sample-service`.
    - Logs query returns logs for `argus-sample-service`.
    - Metrics query returns metrics / dashboard data.
- [x] Air-gap compliance:
  - 100% of container images resolved from internal mirror (`localhost:5001/argus/*`). Zero public pulls at runtime.
- [x] No regressions:
  - Full suite `./scripts/verify.sh` green (all steps pass).

## 2. Edge cases & failure paths (from `verification/edge-cases.md`)
- **Infrastructure / dependency**:
  - ClickHouse temporarily unreachable -> SigNoz API returns 503 or friendly error message, does not crash or exit. Recovers immediately when ClickHouse is restored.
- **Data volume / bounds**:
  - Deep trace (e.g. 100+ spans or large attribute maps) -> query completes within reasonable time window (< 5s).
  - Empty time range -> returns 200 with empty array/result, no panic.
- **Security / Compliance**:
  - Strict air-gap: SigNoz pods must have no egress to internet. Egress verification script checks connection attempts.

## 3. E2E scenario(s)
1. Deploy SigNoz pointing to ClickHouse HA cluster in `argus-system`.
2. OTel Gateway forwards redacted telemetry stream into SigNoz ClickHouse tables.
3. Sample service (`argus-sample-service`) performs synthetic requests.
4. SigNoz API is queried:
   - `GET /api/v1/services` -> includes `argus-sample-service`.
   - `POST /api/v3/query_range` (or traces search API) -> returns traces for the service.
   - Logs explorer API -> returns logs for the service.
5. Verification script asserts 200 OK responses with matching service data and zero unhandled exceptions.

## 4. Plan (thinnest vertical slice)
1. Mirror SigNoz images (`signoz/signoz:v0.145.0` and `signoz/signoz-otel-collector:v0.144.13`) to `localhost:5001/argus/*` and update `deploy/mirror/images.txt`.
2. Apply SigNoz schema migrations on ClickHouse HA cluster.
3. Configure SigNoz deployment manifests in `deploy/signoz/`:
   - ConfigMap with SigNoz configuration (telemetry disabled).
   - Deployment / StatefulSet for SigNoz web + query-service.
   - Service exposing SigNoz on port 8080.
4. Update `deploy/otel/gateway.yaml` to export telemetry to SigNoz collector/ClickHouse so both raw OTel and SigNoz tables receive redacted telemetry.
5. Create deployment script `scripts/deploy-signoz.sh`.
6. Create verification tests:
   - `scripts/test-signoz.sh` (service discovery, traces, logs, dashboards, phone-home verification).
   - `scripts/test-signoz-edge-cases.sh` (ClickHouse unavailable degradation, empty-state, large trace).
7. Integrate into `scripts/verify.sh` and run full test suite.
