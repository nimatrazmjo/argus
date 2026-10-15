# ADR-0008: Service Level Objectives (SLO), Error Budget Burndown, and Multi-Window Burn Rate Tracking

- **Status**: Accepted
- **Date**: 2026-10-15
- **Author**: SRE / Observability Platform Engineer

## Context
Project Argus requires quantifiable, standardized reliability targets across instrumented microservices (Feature F012). Rather than relying solely on raw threshold alerts that cause alert fatigue, the platform must implement modern Site Reliability Engineering (SRE) principles:
1. **Service Level Indicators (SLIs)**: Measurable ratios of good events over total valid events (availability and latency).
2. **Service Level Objectives (SLOs)**: Target reliability thresholds (e.g. 99.0% availability over a rolling window).
3. **Error Budgets & Burndown**: The allowable unreliability budget ($100\% - SLO$). Consumption must be tracked continuously.
4. **Multi-Window Burn-Rate Alerting**: Fast burn rate detection (consuming significant error budget rapidly, e.g. 2% in 1 hour @ 14.4x burn rate) and slow burn rate detection (consuming 5% in 6 hours @ 6.0x burn rate).
5. **Air-Gap Compliance**: Dashboards, metrics, and alerting must function 100% air-gapped without SaaS dependencies (e.g. Datadog SLO, Nobl9, or external CDNs).

## Decision
We establish **OpenSLO-Compatible SLO & Error Budget Tracking** integrated across the Argus telemetry spine, application runtime, and SigNoz Ruler engine.

Key implementation components:
1. **Declarative OpenSLO Manifests**:
   - SLO definitions are authored declaratively in `deploy/slo/slo-definition.json` complying with the OpenSLO v1 specification.
   - Defines an Availability SLI ($\text{HTTP status} < 500$) with a 99.0% objective target and a Latency SLI ($\text{duration} \le 500\text{ms}$) with a 95.0% objective target over rolling evaluation windows.
2. **In-Engine SLI Accounting & Metric Emission**:
   - `argus-sample-service` embeds a high-performance, thread-safe sliding window SLI accountant.
   - Computes:
     - Availability SLI: $\text{Good Requests} / \text{Total Requests}$
     - Error Budget Consumed: $\frac{\text{Error Rate}}{1 - \text{SLO Target}} \times 100\%$
     - Error Budget Remaining: $\max(0.0, 100\% - \text{Consumed})$
     - Burn Rate: $\frac{\text{Error Rate}}{1 - \text{SLO Target}}$
   - Emits OpenTelemetry metrics to the collector: `argus_slo_sli_ratio`, `argus_slo_error_budget_remaining_percent`, and `argus_slo_burn_rate`.
3. **Multi-Window Burn Rate Alerting**:
   - Declarative alert rules in `deploy/slo/slo-rules.json` are synchronized to the SigNoz Ruler via `deploy/slo/apply-slo.sh`.
   - Alert tiers:
     - **Fast Burn Rate Alert (`ArgusSLOFastBurnRate`)**: Fires if burn rate $> 14.4$ (would exhaust budget in $\approx 2$ days; burns 2% of budget in 1 hour). Severity: `critical`.
     - **Slow Burn Rate Alert (`ArgusSLOSlowBurnRate`)**: Fires if burn rate $> 6.0$ (burns 5% of budget in 6 hours). Severity: `warning`.
     - **Budget Exhausted Alert (`ArgusSLOBudgetExhausted`)**: Fires if error budget remaining drops to $0\%$. Severity: `critical`.
4. **Air-Gapped Visual SLO Dashboard**:
   - Exposed directly by the service at `GET /slo`, rendering a self-contained, high-contrast dark theme dashboard (Argus styling).
   - Features real-time error budget burndown progress bars, SLI health badges (`HEALTHY`, `BURNING_FAST`, `BURNING_SLOW`, `BUDGET_EXHAUSTED`, `NO_TRAFFIC`), latency breakdown, and manual counter reset capability.
   - Also exposes machine-readable JSON telemetry at `GET /api/slo` and reset trigger at `POST /api/slo/reset`.
5. **Edge Case Safety**:
   - **No-Traffic Window / Cold Start**: Zero division is explicitly guarded. If $\text{Total Requests} = 0$, the engine reports $100\%$ SLI, $0.0$ burn rate, $100\%$ remaining budget, and status `NO_TRAFFIC`.
   - **Budget Exhaustion**: When errors exceed total budget, remaining budget clamps cleanly at $0.0\%$, and the system flags `BUDGET_EXHAUSTED`.
   - **Independent Latency Breach**: Requests with status 200 that exceed latency thresholds ($> 500\text{ms}$) degrade latency SLI without corrupting availability SLI.

## Consequences
- **Positive**:
  - Eliminates alert fatigue by alerting on rate of budget consumption rather than raw momentary error spikes.
  - Gives product owners and SREs explicit, objective visibility into release velocity vs. stability tradeoffs.
  - Native integration with SigNoz Ruler and OTel Collector preserves single-pane-of-glass architecture.
  - Fully self-contained and zero-egress, safe for classified/air-gapped operations.
- **Negative / Constraints**:
  - In-memory window tracking on microservices resets upon container restart unless backed by persistent ClickHouse materialized aggregations.

## Alternatives Considered
- **Nobl9 / Sloth standalone SLO operators**: Considered running third-party Prometheus-operator companion CRDs. Rejected to avoid third-party binary maintenance in the air-gap mirror and because SigNoz Ruler natively evaluates the underlying PromQL expressions.
