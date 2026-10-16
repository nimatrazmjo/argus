# ADR-0012: Real User Monitoring (RUM) & DOM Session Replay Architecture

## Status
Accepted

## Context
Project Argus requires client-side Real User Monitoring (RUM) and DOM session replay (Feature F017) to provide complete frontend observability, user interaction diagnostics, and visual bug reproduction for web applications.

Key architectural considerations:
1. **Tool Selection (OpenReplay vs. HyperDX vs. SigNoz)**:
   - SigNoz provides robust backend OpenTelemetry APM (traces, logs, metrics, ClickHouse HA) but lacks native DOM session replay (visual `rrweb` DOM mutation playback, mouse movements, click tracking).
   - HyperDX attempts full-stack APM replacement, which conflicts with Argus's established SigNoz and OpenTelemetry Operator baseline.
   - OpenReplay's session replay model (DOM mutation tree tracking via `rrweb` standards, privacy redaction pipeline, and timeline playback) provides dedicated frontend replay without displacing SigNoz.
2. **Coexistence with SigNoz**:
   - The RUM engine sits *beside* SigNoz rather than replacing it.
   - Frontend web transactions generate W3C `traceparent` headers that correlate client-side user sessions (`sessionId`) with backend distributed traces (`traceId`) in SigNoz, enabling seamless 1-click drill-down from an APM trace error to the corresponding session replay.
3. **Air-Gap Compliance**:
   - Public SaaS replay tools (LogRocket, FullStory) violate air-gap federal isolation mandates.
   - The RUM collector daemon (`argus-rum-collector`) runs entirely in-cluster using the mirrored `localhost:5001/argus/python:3.12-alpine` image with zero external egress.
4. **PII Masking & Privacy Mandate (Consistent with F005)**:
   - Form inputs with sensitive types (`password`, `hidden`), data privacy attributes (`data-openreplay-masked`, `class="masked"`), credit cards, SSNs, and authorization tokens must be masked client-side before transmission.
   - The ingestion gateway must enforce an additional server-side regex sanitization pass to prevent data leakage in case of misconfigured client trackers.

## Decision
1. **Deploy Air-Gapped In-Cluster RUM Collector & Replay Engine (`argus-rum-collector`)**:
   - Runs as a Kubernetes Deployment and Service in `argus-system` on port `8082`.
   - Exposes:
     - `POST /v1/rum/ingest`: High-throughput beacon ingestion with schema validation and secondary PII sanitization.
     - `GET /v1/rum/tracker.js`: Lightweight, zero-dependency client tracker script served directly from the cluster.
     - `GET /v1/rum/sessions`: REST API for session listing, filtering, and query by user, tag, or trace ID.
     - `GET /v1/rum/replay/<session_id>`: JSON timeline of sanitized DOM snapshots and user events.
     - `GET /v1/rum/player/<session_id>`: Visual DOM replay player with scrubbing timeline, event inspector, and masked element rendering.
     - `GET /metrics`: Prometheus metrics (`argus_rum_sessions_total`, `argus_rum_events_total`, `argus_rum_pii_redacted_total`).
2. **Data Storage in ClickHouse**:
   - RUM metadata and event streams are stored in ClickHouse in dedicated tables (`default.rum_sessions` and `default.rum_events`), leveraging ClickHouse's high compression and columnar query speed.
3. **Multi-Tier Privacy & PII Redaction Pipeline**:
   - **Tier 1 (Client Tracker)**: Inputs of type `password`, `tel`, credit-card fields, and elements with `data-masked="true"` or `class="masked"` are replaced with `***` or `[REDACTED]` before leaving the browser.
   - **Tier 2 (Gateway Sanitizer)**: Strict regular expression filters on email patterns, PAN/credit cards (`\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b`), SSNs (`\b\d{3}-\d{2}-\d{4}\b`), and Bearer tokens.
4. **Frontend Integration in Sample App**:
   - `argus-sample-service` embeds the RUM tracker on its interactive web pages (`/checkout`, `/slo`), enabling end-to-end verification of user session capture, PII masking, and backend trace correlation.

## Consequences
- **Positive**:
  - Full client-side session replay capability without compromising air-gap isolation.
  - Strict privacy guarantees with defense-in-depth PII masking.
  - Bi-directional correlation between client sessions and SigNoz APM traces.
  - Zero conflict with existing backend OpenTelemetry pipelines.
- **Negative / Trade-offs**:
  - High-traffic DOM mutation recordings can consume significant storage if session retention is not bounded by downsampling or sampling rate controls.
