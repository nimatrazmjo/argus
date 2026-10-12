# Phase 05 — AIOps / the moat

The differentiated layer — anomaly detection, correlation, and an LLM query/summary surface.
Deferred and optional; the platform is fully useful without it. Depends on green Phase 04 (or
Phase 03 if Phase 04 is skipped). Build a thin slice and validate before deepening.

## F019 — Anomaly + forecast monitors
**Status**: NOT STARTED
### Acceptance criteria
- [ ] At least one metric has a dynamic monitor (seasonal decomposition or EWMA baseline) that fires on true anomalies, not fixed thresholds.
- [ ] Measured false-positive rate on a replayed week of data is reported.
- [ ] Edge cases: seasonality shift, sparse data, cold start.
- [ ] E2E: injected anomaly fires; normal variation does not.
- [ ] FULL verify green.

## F020 — Alert correlation + root-cause grouping
**Status**: NOT STARTED
### Acceptance criteria
- [ ] Related alerts across services group into one incident with a probable-cause ranking.
- [ ] Edge cases: unrelated-but-simultaneous alerts not falsely merged.
- [ ] E2E: a cascading failure produces one grouped incident, not N pages.
- [ ] FULL verify green.

## F021 — NL query + incident summarization (LLM)
**Status**: NOT STARTED
### Acceptance criteria
- [ ] A natural-language query returns the right telemetry (NL -> ClickHouse SQL) for a defined question set; incidents get an auto-summary.
- [ ] LLM backend runs within the agency boundary (Bedrock in the approved GovCloud boundary, or an on-prem model) — no data leaves the boundary.
- [ ] Edge cases: ambiguous query, hallucinated field rejected, prompt-injection from log content neutralized.
- [ ] E2E: the query set returns correct results; an incident summary is generated.
- [ ] FULL verify green.

## Phase completion criteria
F019-F021 `COMPLETE` with evidence, with measured quality (false-positive rate, correlation
accuracy, query correctness), and no telemetry leaving the agency boundary.
