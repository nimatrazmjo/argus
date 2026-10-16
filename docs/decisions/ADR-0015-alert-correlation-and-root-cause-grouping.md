# ADR-0015: Topological Alert Correlation & Probable Root-Cause Grouping

- **Status**: Accepted
- **Date**: 2026-10-15
- **Author**: SRE / Observability & AIOps Platform Engineer

## Context
In microservice architectures deployed across federal and enterprise cloud environments (such as DHS Argus), failures propagate rapidly through service dependency graphs. A single root-cause failure (e.g., database connection pool exhaustion or network partition) cascades through upstream calling services, generating a storm of downstream alerts within seconds:
1. `chi-argus-clickhouse`: `DatabaseConnectionPoolExhausted` (t0)
2. `argus-sample-service`: `ServiceHigh5xxErrorRate` (t0 + 4s)
3. `argus-auto-service`: `HTTPUpstreamRequestTimeout` (t0 + 8s)
4. `argus-synthetic-probe`: `SyntheticCanaryProbeFailure` (t0 + 12s)

Without alert correlation, standard Alertmanager routing emits N distinct pages to on-call engineers, splintering situational awareness, triggering alert fatigue, and delaying Mean Time to Identify (MTTI) and Mean Time to Resolve (MTTR).

Feature F020 requires an intelligent, deterministic alert correlation engine that:
1. Clusters temporally co-occurring alerts into a single cohesive incident based on runtime service topology (F007/F008 auto-instrumentation and eBPF traces).
2. Computes an interpretable probable-cause ranking that isolates the upstream root cause from downstream symptoms.
3. Quantifies blast radius and traces causal propagation paths.
4. Prevents false merges: unrelated-but-simultaneous alerts occurring in disjoint service boundaries or distinct tenants must remain strictly separate.
5. Emits exactly one consolidated incident ticket to incident management (ServiceNow Table API) with dynamic symptom appending.
6. Operates 100% air-gapped without external SaaS, proprietary AI, or outbound cloud dependencies.

## Decision
We implement **`argus-correlation-engine`** as an in-cluster AIOps microservice listening on port `9097` in the `argus-system` namespace.

Key architectural mechanisms:
1. **Topological Dependency Graph**:
   - Maintains a directed graph $G = (V, E)$ where vertices $V$ represent services and directed edges $(u, v) \in E$ represent dependency relationships ($u$ calls $v$, meaning $u$ depends on $v$).
   - Topology is seeded from instrumented traces (F007/F008) and dynamically extensible via `/api/topology` REST endpoints.
2. **Sliding Temporal Clustering Window**:
   - Evaluates alerts arriving within a sliding correlation window $T_{\text{corr}} = 120\text{s}$ (configurable via `CORRELATION_WINDOW_SECONDS`).
   - Alerts arriving within $T_{\text{corr}}$ whose services are topologically connected (reachable in $G$ or sharing a causal ancestor/descendant relationship) are grouped into the same incident cluster.
3. **Probable-Cause Ranking Algorithm**:
   - For each alert $a_i \in C$ in an incident cluster:
     $$\text{Score}(a_i) = w_{\text{topo}} \cdot \text{DepthRank}(a_i) + w_{\text{time}} \cdot \text{TemporalPrecedence}(a_i) + w_{\text{type}} \cdot \text{FailureCriticality}(a_i)$$
   - **Topological Depth ($w_{\text{topo}} = 0.50$)**: Evaluates upstream position in the failure subgraph. The service that is an in-tree ancestor with in-degree 0 in the failure subgraph is the upstream root.
   - **Temporal Precedence ($w_{\text{time}} = 0.30$)**: Earliest alert timestamp receives maximum score, accounting for metric scrape delays.
   - **Failure Criticality ($w_{\text{type}} = 0.20$)**: Foundational failures (database connection drop, disk/memory saturation, infrastructure faults) carry higher intrinsic causal weights than generic symptoms (HTTP 500s, probe timeouts).
   - The alert with the highest composite score is designated `Probable Root Cause` (with confidence metric $\ge 0.90$); all other alerts are structured as `Downstream Symptoms` with topological hop distance.
4. **Disjoint Boundary Protection (Anti-False-Merge Guardrail)**:
   - When alerts fire simultaneously on topologically disjoint components (e.g., `argus-payment-service` and `argus-auth-service`), the reachability test returns false, and the engine strictly creates distinct, unmerged incidents.
   - Multi-tenant boundaries (`tenant_id`) enforce strict correlation isolation.
5. **Out-of-Order Re-ranking & Dynamic Appending**:
   - When a symptom alert arrives before the root cause alert, the engine creates the initial incident and, upon receipt of the upstream root cause alert, dynamically updates the probable root cause, re-ranks symptoms, and updates the existing ServiceNow ticket via PATCH without ticket fluttering.
6. **ServiceNow Incident Pipeline Integration**:
   - Dispatches a single correlated incident payload to ServiceNow (`/api/now/table/incident`):
     - `short_description`: `[ARGUS CORRELATED] Root Cause: <root_service> (<root_alert>) - <N> symptoms grouped`
     - `work_notes`: Detailed causal ranking, blast radius list, and dependency propagation path.
     - Resolves the ticket when all constituent alerts report `status: resolved`.

## Consequences
- **Positive**:
  - Reduces on-call alert volume by 75–90% during cascading outages.
  - Decreases MTTI by pinpointing the root cause service and alert immediately in the incident header.
  - Eliminates false merges for simultaneous unrelated incidents.
  - Fully air-gapped, zero external dependencies, FedRAMP/DoD IL-5 compliant.
- **Negative / Constraints**:
  - Accuracy relies on maintaining an up-to-date service topology map.
  - The correlation window ($120\text{s}$) introduces a trade-off: larger windows catch slow-propagating cascades but risk grouping loosely related anomalies.

## Alternatives Considered
- **Purely Time-Based Clustering (PagerDuty Intelligent Alert Grouping)**: Rejected because unrelated simultaneous alerts across independent services get erroneously merged into single incidents.
- **Heavy Machine Learning / Graph Neural Networks**: Rejected due to high operational complexity, non-deterministic explainability, and resource consumption in air-gapped container environments compared to topological graph traversal and deterministic scoring.
