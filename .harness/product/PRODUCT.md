# PRODUCT — the vision

## What Argus is
Argus is a self-hosted observability platform for internal use at DHS — a Datadog-equivalent
that runs entirely inside Kubernetes, on-prem and air-gapped, with no external SaaS
dependency and no telemetry leaving the agency boundary. It unifies metrics, logs, and traces
for the agency's applications behind a single pane of glass.

## The problem
Commercial observability (Datadog) is expensive at scale and sends telemetry to a vendor
cloud, which is a non-starter for air-gapped government workloads carrying regulated data.
Teams need the same "see everything, correlate in one click" experience, but inside their own
cluster, under their own ATO, with PII/CJIS-safe handling of logs and traces.

## The core idea
One OpenTelemetry-native pipeline into one columnar store, read through one UI. The fewest
moving parts that cover Datadog's day-to-day surface — because in a government environment
every distinct component is a separate ATO, scan, and patch burden. The spine is
OpenTelemetry Collector -> ClickHouse -> SigNoz. Onboarding a new service must be a one-line
change (an OTel Operator annotation), so the platform scales from ~10 apps today to ~50
without per-app toil.

## The shape of the MVP ("done enough to use")
- A sample service emits a metric, a trace, and a log, and all three correlate by trace id in
  the UI — proven end to end, air-gapped, with PII redaction on.
- Any team onboards a service with one annotation and sees it in the UI.
- Infra (nodes, pods) and backend APM are visible without hand-instrumentation.
- Alerts fire and route to the agency's incident tooling.

## What makes it different (the non-negotiables)
- Air-gapped: every image/chart mirrored to an internal registry; usage telemetry disabled.
- Compliant by construction: PII/CJIS redaction at ingest, before data reaches storage.
- Small ATO surface: a unified stack, not four independently-scaled subsystems.
- Cost-controlled: tiered retention + metric downsampling + cardinality guardrails from day one.

## Scope boundary (what Argus is NOT, for now)
Not a SaaS product and not multi-customer. Not a SIEM / security platform (Falco, Wazuh, Trivy
are separate efforts). The ML/AIOps "Watchdog" layer (anomaly, root-cause, NL query) is the
final, optional phase — the platform is useful long before it exists.
