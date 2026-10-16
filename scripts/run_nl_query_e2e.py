#!/usr/bin/env python3
"""
Argus Feature F021: Natural Language Telemetry Query (NL-to-SQL) & Incident Summarization E2E.
Validates:
1. Healthcheck & GovCloud Bedrock in-boundary configuration.
2. Observability schema catalog verification.
3. Defined question set NL-to-SQL translation benchmarks (traces, metrics, logs, RUM).
4. GovCloud air-gap egress firewall audit (zero unauthorized public commercial LLM calls).
5. Incident auto-summarization on F020 cascading failure graph.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

LLM_URL = os.environ.get(
    "LLM_URL", "http://argus-aiops-llm.argus-system.svc.cluster.local:9098"
).rstrip("/")
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "/tmp/evidence-f021")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

AUTH_HEADER = {"Authorization": "Bearer test-token-admin", "Content-Type": "application/json"}

def http_json(url: str, method: str = "GET", data: dict = None, headers: dict = None) -> dict:
    req_headers = dict(AUTH_HEADER)
    if headers:
        req_headers.update(headers)
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        headers=req_headers,
        method=method
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}

def main():
    print("=================================================================")
    print("  FEATURE F021: NL QUERY & INCIDENT SUMMARIZATION E2E BATTERY    ")
    print("=================================================================")

    # Step 1: Healthcheck & GovCloud in-boundary verification
    print("\n[Step 1] Verifying AIOps LLM Service Health & GovCloud Boundary...")
    health = http_json(f"{LLM_URL}/healthz")
    print(f"[+] Healthcheck: {health}")
    assert health.get("status") == "ok", "LLM service healthcheck failed"
    assert health.get("region") == "us-gov-west-1", "GovCloud region mismatch"
    assert health.get("boundary") == "FEDRAMP_GOVCLOUD_AIRGAP", "Boundary compliance mismatch"

    # Step 2: Observability Schema Catalog Verification
    print("\n[Step 2] Verifying Observability Schema Catalog...")
    schema_resp = http_json(f"{LLM_URL}/api/schema")
    schemas = schema_resp.get("schema", {})
    required_tables = ["otel_traces", "otel_metrics_gauge", "otel_metrics_sum", "otel_logs", "rum_events"]
    for t in required_tables:
        assert t in schemas, f"Required table {t} missing from schema catalog"
        print(f"[+] Verified schema table: {t} ({len(schemas[t]['columns'])} columns)")

    # Step 3: Defined Question Set NL-to-SQL Translation Benchmarks
    print("\n[Step 3] Running Defined Question Set NL-to-SQL Translation Benchmark...")
    benchmark_questions = [
        {
            "id": "Q1_SLOW_ENDPOINTS",
            "query": "Show me the top 5 slowest endpoints by p95 latency in the last hour",
            "expected_table": "otel_traces",
            "expected_clauses": ["quantile(0.95)", "p95_latency_ms", "LIMIT 5"]
        },
        {
            "id": "Q2_ERROR_RATE",
            "query": "What is the error rate for sample-service in the last 15 minutes?",
            "expected_table": "otel_traces",
            "expected_clauses": ["STATUS_CODE_ERROR", "error_rate_pct", "argus-sample-service"]
        },
        {
            "id": "Q3_CRITICAL_LOGS",
            "query": "List all critical logs mentioning connection timeout",
            "expected_table": "otel_logs",
            "expected_clauses": ["SeverityText", "ERROR", "timeout", "LIMIT 20"]
        },
        {
            "id": "Q4_CPU_UTILIZATION",
            "query": "What is the average CPU utilization per node in the cluster?",
            "expected_table": "otel_metrics_gauge",
            "expected_clauses": ["MetricName", "host.name", "avg_value"]
        },
        {
            "id": "Q5_RUM_ERRORS",
            "query": "How many user sessions experienced page errors in RUM?",
            "expected_table": "rum_events",
            "expected_clauses": ["count(DISTINCT session_id)", "event_type = 'error'"]
        }
    ]

    benchmark_results = []
    for q in benchmark_questions:
        t0 = time.time()
        resp = http_json(f"{LLM_URL}/api/nl-query", method="POST", data={"query": q["query"]})
        latency_ms = round((time.time() - t0) * 1000, 2)

        status = resp.get("status")
        sql = resp.get("generated_sql", "")
        print(f"\n  [{q['id']}] Query: '{q['query']}'")
        print(f"      -> Status: {status} (Latency: {latency_ms}ms)")
        print(f"      -> SQL: {sql}")

        assert status == "ok", f"Query {q['id']} failed with response: {resp}"
        assert q["expected_table"] in sql, f"Query {q['id']} did not reference {q['expected_table']}"
        for clause in q["expected_clauses"]:
            assert clause.lower() in sql.lower(), f"Clause '{clause}' missing from SQL: {sql}"

        benchmark_results.append({
            "id": q["id"],
            "query": q["query"],
            "status": "PASS",
            "latency_ms": latency_ms,
            "generated_sql": sql,
            "domain": resp.get("domain")
        })

    avg_latency = round(sum(r["latency_ms"] for r in benchmark_results) / len(benchmark_results), 2)
    benchmark_report = {
        "timestamp": time.time(),
        "total_queries_tested": len(benchmark_results),
        "translation_accuracy_pct": 100.0,
        "average_translation_latency_ms": avg_latency,
        "boundary_tested": "US_GOVCLOUD_BEDROCK_AIRGAP",
        "results": benchmark_results
    }
    with open(os.path.join(EVIDENCE_DIR, "nl-to-sql-benchmarks.json"), "w") as f:
        json.dump(benchmark_report, f, indent=2)
    print(f"\n[+] NL-to-SQL translation benchmarks saved to {EVIDENCE_DIR}/nl-to-sql-benchmarks.json (Avg latency: {avg_latency}ms)")

    # Step 4: GovCloud Air-Gap & Commercial Egress Proof
    print("\n[Step 4] Auditing GovCloud Bedrock Egress Firewall & Air-Gap Compliance...")
    egress_audit = http_json(f"{LLM_URL}/api/egress/audit")
    print(f"[+] Egress Audit Status: {egress_audit.get('egress_audit_status')}")
    print(f"[+] Agency Boundary: {egress_audit.get('agency_boundary')}")
    print(f"[+] Unauthorized External Requests: {egress_audit.get('unauthorized_external_requests')}")
    print(f"[+] Blocked Commercial Endpoints: {egress_audit.get('public_commercial_apis_blocked')}")

    assert egress_audit.get("egress_audit_status") == "COMPLIANT"
    assert egress_audit.get("unauthorized_external_requests") == 0, "Unauthorized external requests detected!"

    with open(os.path.join(EVIDENCE_DIR, "govcloud-bedrock-egress-proof.json"), "w") as f:
        json.dump(egress_audit, f, indent=2)
    print(f"[+] GovCloud Bedrock egress proof saved to {EVIDENCE_DIR}/govcloud-bedrock-egress-proof.json")

    # Step 5: Incident Auto-Summarization E2E
    print("\n[Step 5] Synthesizing Executive Post-Mortem on F020 Cascading Outage...")
    # Feed correlated cascading failure payload from F020
    incident_payload = {
        "incident_id": "INC-CORR-20261015-001",
        "probable_root_cause": {
            "service": "chi-argus-clickhouse",
            "alertname": "ClickHouseConnectionPoolExhausted",
            "confidence": 0.99,
            "startsAt": "2026-10-15T23:10:00Z"
        },
        "symptoms": [
            {"service": "argus-sample-service", "alertname": "ServiceHigh5xxErrorRate", "hops_from_root": 1},
            {"service": "argus-auto-service", "alertname": "HTTPUpstreamRequestTimeout", "hops_from_root": 2},
            {"service": "argus-synthetic-probe", "alertname": "SyntheticCanaryProbeFailure", "hops_from_root": 3}
        ],
        "blast_radius": ["argus-sample-service", "argus-auto-service", "argus-synthetic-probe"],
        "causal_path": ["chi-argus-clickhouse", "argus-sample-service", "argus-auto-service", "argus-synthetic-probe"],
        "alerts": [
            {"alertname": "ClickHouseConnectionPoolExhausted", "service": "chi-argus-clickhouse"},
            {"alertname": "ServiceHigh5xxErrorRate", "service": "argus-sample-service"},
            {"alertname": "HTTPUpstreamRequestTimeout", "service": "argus-auto-service"},
            {"alertname": "SyntheticCanaryProbeFailure", "service": "argus-synthetic-probe"}
        ]
    }

    t_sum_0 = time.time()
    summary_resp = http_json(f"{LLM_URL}/api/summarize/incident", method="POST", data=incident_payload)
    t_sum_ms = round((time.time() - t_sum_0) * 1000, 2)

    assert summary_resp.get("status") == "ok", f"Summarization failed: {summary_resp}"
    summary = summary_resp.get("summary", {})

    print(f"\n[+] Generated Title: {summary.get('title')}")
    print(f"[+] Executive Summary: {summary.get('executive_summary')[:120]}...")
    print(f"[+] Root Cause Analysis: {summary.get('root_cause_analysis')[:120]}...")
    print(f"[+] Recommended Actions ({len(summary.get('recommended_remediation', []))}):")
    for act in summary.get("recommended_remediation", []):
        print(f"    {act}")

    assert "chi-argus-clickhouse" in summary.get("title")
    assert summary.get("confidence_score") == 0.99
    assert len(summary.get("blast_radius_assessment", {}).get("impacted_services", [])) == 3
    assert len(summary.get("recommended_remediation", [])) == 4

    with open(os.path.join(EVIDENCE_DIR, "incident-summary-output.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[+] Executive incident summary output saved to {EVIDENCE_DIR}/incident-summary-output.json")

    print("\n=================================================================")
    print("STATUS: PASS — Feature F021 NL Query & Summarization Verified 100% Green!")
    print("=================================================================")

if __name__ == "__main__":
    main()
