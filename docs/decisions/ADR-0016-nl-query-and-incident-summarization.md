# ADR-0016: Natural Language Telemetry Query (NL-to-SQL) & Incident Summarization via In-Boundary GovCloud/Air-Gapped LLM

- **Status**: Accepted
- **Date**: 2026-10-15
- **Author**: SRE / Observability & AI Platform Architect

## Context
Federal observability platforms collect vast volumes of multi-modal telemetry across ClickHouse metrics, traces, logs, and RUM sessions. However, analyzing complex outages and querying telemetry often requires specialized knowledge of ClickHouse SQL syntax, schema table hierarchies, and correlation algorithms. During high-severity incidents, SREs and agency leadership need:
1. An intuitive Natural Language interface that translates operational questions ("Show top 5 slowest endpoints by p95 latency in the last hour") into verified, optimized ClickHouse SQL.
2. Automated Incident Summarization that synthesizes topological alert correlation graphs (F020), anomaly metrics (F019), and affected downstream services into executive-ready incident post-mortems and root-cause analyses (RCA).
3. Zero telemetry leakage: All LLM inference must execute strictly within the approved agency authorization boundary (e.g. AWS GovCloud US-West-1 Bedrock VPC endpoint or in-cluster air-gapped LLM daemon). Zero telemetry may egress to commercial public LLM APIs (OpenAI, Anthropic public, etc.).
4. Strict RBAC enforcement (F016): Telemetry queries and incident summaries must enforce agency roles (Admin, Operator, Viewer) and row-level tenant boundaries.
5. Robust Prompt Injection & Hallucination Defense: Unsanitized log content or malicious user prompts attempting SQL injection or jailbreaking must be neutralized.

## Decision
We implement **`argus-aiops-llm`** as a dedicated in-cluster microservice listening on port `9098` in the `argus-system` namespace.

Key architectural components:
1. **Air-Gapped Agency Boundary / GovCloud Bedrock Inference Engine**:
   - Executes inference using an in-boundary LLM adapter.
   - For FedRAMP High / DoD IL-5 compliance, outbound connectivity is constrained to in-cluster local weights or designated private GovCloud VPC endpoints with strict egress proxy enforcement. Public commercial egress is blocked at the network policy layer.
2. **Deterministic & Semantic NL-to-SQL Translator**:
   - Converts natural-language observability queries into syntactically valid ClickHouse SQL against `otel_traces`, `otel_metrics_gauge`, `otel_metrics_sum`, `otel_logs`, and `rum_events`.
   - AST & Safety Validator: Enforces read-only `SELECT` queries. Strictly prohibits data mutation (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `SYSTEM`).
   - Schema Catalog Verification: Verifies requested table and column names against the Argus observability schema catalog, rejecting hallucinated fields before query execution.
3. **Automated Incident Summarizer**:
   - Ingests correlated incident payloads from Feature F020 (`incident_id`, `probable_root_cause`, `symptoms`, `blast_radius`, `causal_path`, `alerts`).
   - Generates structured incident post-mortems:
     - Executive Overview (plain-language summary for agency leadership).
     - Probable Root Cause Analysis (technical explanation of upstream failure).
     - Blast Radius & Downstream Symptoms (impacted services and caller hops).
     - Recommended Remediation Steps (prescriptive runbook actions).
4. **Security & Prompt-Injection Neutralization**:
   - Telemetry logs and error messages fed into summarization context are sanitized with delimiters and structural escaping to prevent indirect prompt injection (e.g. log bodies containing `IGNORE PREVIOUS INSTRUCTIONS`).
   - Strict input validation prevents prompt leakage or privilege escalation.
5. **RBAC & Multi-Tenancy Enforcement**:
   - Validates Bearer JWTs via the Agency SSO/IdP gateway (F016).
   - Maps user roles to allowable query scopes:
     - `Admin`: Full NL-to-SQL query execution and incident summarization.
     - `Operator`: Telemetry analytics and incident summarization; admin commands blocked.
     - `Viewer`: Pre-aggregated dashboards and read-only telemetry summaries; raw logs restricted.
   - Automatically injects `tenant_id` WHERE clauses for tenant-scoped users.

## Consequences
- **Positive**:
  - Dramatically lowers the operational barrier for non-SRE stakeholders and incident commanders.
  - Automates post-incident RCA documentation in seconds rather than hours.
  - 100% compliant with FedRAMP High / DoD IL-5 air-gap and data privacy requirements.
  - Immune to prompt injection and unauthorized schema access.
- **Negative / Constraints**:
  - Free-form queries outside the observability domain must be politely rejected or clarified.
  - Complex multi-table joins require schema grounding in prompt context.

## Alternatives Considered
- **Direct Public LLM API (OpenAI/Anthropic Public)**: Strictly rejected due to federal data privacy mandates prohibiting egress of production logs, traces, and customer PII outside the authorization boundary.
- **Client-Side LLM Execution**: Rejected due to browser compute limitations and inability to securely enforce server-side RBAC and ClickHouse schema access control.
