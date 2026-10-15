# ADR-0009: Paging Path, Webhook Gateway & ServiceNow Incident Routing

## Status
Accepted

## Context
Argus requires an air-gapped, resilient incident paging and routing mechanism (Feature F013) to bridge firing monitoring alerts from SigNoz/Alertmanager to enterprise agency incident management tooling (specifically ServiceNow Incident Management and internal correlation tools like Keep). 

In DHS and federal operational environments:
1. Commercial SaaS notification providers (PagerDuty, Opsgenie) are disallowed due to FedRAMP High / air-gap network isolation constraints.
2. Alert notifications must be translated into standardized enterprise ITSM formats (ServiceNow Table API `incident` schema).
3. Transient destination outages or network maintenance windows must never cause alert notifications to be silently lost.
4. Rapidly re-firing or flapping alerts must be deduplicated to avoid notification storms and duplicate ticket creation in ServiceNow.

## Decision
1. **Paging Gateway (`argus-paging-gateway`)**:
   - Stand up a lightweight, containerized webhook dispatcher (`argus-paging-gateway`) deployed in `argus-system`.
   - Expose endpoint `POST /webhook/alert` adhering to the Prometheus Alertmanager webhook protocol.
   - Map Alertmanager alerts to ServiceNow REST Table API payloads (`POST /api/now/table/incident`):
     - `short_description`: Alert title and primary resource context.
     - `description`: Alert annotations, metric query expressions, and affected components.
     - `severity`/`urgency`: Critical (1), Warning (2), Info (3).
     - `correlation_id`: Alert fingerprint for idempotent deduplication and state updates.
     - `state`: New (1) on `firing`, Resolved (6) on `resolved`.
2. **Resilience & Queueing Mechanism**:
   - In-memory thread-safe retry queue with exponential backoff (initial delay 1s, backoff factor 2x, max 5 retries).
   - If ServiceNow returns transient errors (HTTP 5xx, timeout, connection refused), pending payloads are queued and flushed asynchronously upon recovery.
3. **Duplicate Suppression**:
   - Sliding suppression window keyed by `correlation_id` (alert fingerprint).
   - Firing alerts received while an incident is already open for that fingerprint update the work notes of the existing ticket instead of creating new duplicates.
4. **Mock ServiceNow Receiver for E2E Verification**:
   - In air-gapped testing and CI, an in-cluster mock server (`argus-servicenow-mock`) implements the ServiceNow Table API (`/api/now/table/incident`) with state management, query API, and simulated outage controls (`/api/simulate/fail`).

## Consequences
- **Positive**:
  - Full air-gap compliance with zero external dependencies.
  - Native integration with Alertmanager and SigNoz Ruler webhook channels.
  - Zero loss of alerts during destination maintenance windows via queueing.
  - Prevents alert storms and duplicate ticket explosion in agency ITSM.
- **Negative / Trade-offs**:
  - Requires maintaining the gateway bridge container in `argus-system`.
