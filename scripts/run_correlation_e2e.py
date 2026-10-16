#!/usr/bin/env python3
"""
Argus Feature F020: Topological Alert Correlation & Root-Cause Grouping E2E Verification.
Validates:
1. Topology graph queries and dependency reachability.
2. Cascading multi-service failure alert grouping into a single incident.
3. Multi-factor probable root-cause ranking (upstream database isolated from downstream symptoms).
4. Blast radius calculation and causal path tracing.
5. ServiceNow Table API dispatch and duplicate page suppression (1 ticket instead of N pages).
6. Alert resolution state synchronization.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

CORRELATION_URL = os.environ.get(
    "CORRELATION_URL", "http://argus-correlation-engine.argus-system.svc.cluster.local:9097"
).rstrip("/")
SERVICENOW_URL = os.environ.get(
    "SERVICENOW_URL", "http://argus-servicenow-mock.argus-system.svc.cluster.local:8088"
).rstrip("/")
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "/tmp/evidence-f020")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

def http_json(url: str, method: str = "GET", data: dict = None) -> dict:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        content = resp.read().decode("utf-8")
        return json.loads(content) if content else {}

def main():
    print("=================================================================")
    print("  FEATURE F020: TOPOLOGICAL ALERT CORRELATION E2E BATTERY        ")
    print("=================================================================")

    # Step 1: Daemon Health & Topology Retrieval
    print("\n[Step 1] Verifying Correlation Engine Health & Topology DAG...")
    health = http_json(f"{CORRELATION_URL}/healthz")
    print(f"[+] Healthcheck: {health}")
    assert health.get("status") == "ok", "Correlation Engine healthcheck failed"

    topology = http_json(f"{CORRELATION_URL}/api/topology")
    nodes = topology.get("nodes", [])
    edges = topology.get("edges", [])
    print(f"[+] Topology DAG retrieved: {len(nodes)} nodes, {len(edges)} directed edges")
    for req_node in ["chi-argus-clickhouse", "argus-sample-service", "argus-auto-service", "argus-synthetic-probe"]:
        assert req_node in nodes, f"Required node {req_node} missing from topology"

    with open(os.path.join(EVIDENCE_DIR, "correlation-topology.json"), "w") as f:
        json.dump(topology, f, indent=2)
    print(f"[+] Topology evidence saved to {EVIDENCE_DIR}/correlation-topology.json")

    # Step 2: Clean Baseline State
    print("\n[Step 2] Resetting Correlation Engine & ServiceNow Mock state...")
    http_json(f"{CORRELATION_URL}/api/reset", method="POST")
    try:
        http_json(f"{SERVICENOW_URL}/api/now/table/incident", method="DELETE")
    except Exception:
        pass
    print("[+] State reset complete.")

    # Step 3: Cascading Failure Simulation
    # Chain: chi-argus-clickhouse (fails first) -> argus-sample-service (500s) -> argus-auto-service (timeout) -> argus-synthetic-probe (probe fail)
    print("\n[Step 3] Simulating Cascading Outage across 4 Dependent Services...")
    t0 = time.time()
    cascade_alerts = [
        {
            "status": "firing",
            "labels": {
                "alertname": "ClickHouseConnectionPoolExhausted",
                "service": "chi-argus-clickhouse",
                "severity": "critical",
                "component": "database",
                "tier": "backend"
            },
            "annotations": {
                "summary": "ClickHouse max client connection pool saturated",
                "description": "Connection pool reached 100/100 active TCP sockets"
            },
            "startsAt": "2026-10-15T23:10:00Z"
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "ServiceHigh5xxErrorRate",
                "service": "argus-sample-service",
                "severity": "critical",
                "component": "order-api",
                "tier": "business-logic"
            },
            "annotations": {
                "summary": "Sample Service 5xx HTTP error rate breached 25%",
                "description": "Upstream ClickHouse query failed with connection timeout"
            },
            "startsAt": "2026-10-15T23:10:03Z"
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "HTTPUpstreamRequestTimeout",
                "service": "argus-auto-service",
                "severity": "warning",
                "component": "api-gateway",
                "tier": "edge"
            },
            "annotations": {
                "summary": "Gateway upstream requests timing out to sample service",
                "description": "p99 latency > 2500ms on /orders endpoint"
            },
            "startsAt": "2026-10-15T23:10:06Z"
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "SyntheticCanaryProbeFailure",
                "service": "argus-synthetic-probe",
                "severity": "warning",
                "component": "blackbox-canary",
                "tier": "synthetics"
            },
            "annotations": {
                "summary": "Synthetic checkout flow canary failing",
                "description": "Playwright synthetic probe returned HTTP 504 Gateway Timeout"
            },
            "startsAt": "2026-10-15T23:10:09Z"
        }
    ]

    # Ingest alerts sequentially simulating propagation delays
    for idx, alert in enumerate(cascade_alerts):
        resp = http_json(f"{CORRELATION_URL}/webhook/alert", method="POST", data=alert)
        res = resp.get("results", [{}])[0]
        print(f"  [{idx+1}/4] Dispatched {alert['labels']['alertname']} on {alert['labels']['service']} -> Action: {res.get('action')}")
        time.sleep(0.3)

    # Step 4: Verify Incident Grouping
    print("\n[Step 4] Verifying Incident Grouping & Alert Storm Suppression...")
    incidents_resp = http_json(f"{CORRELATION_URL}/api/incidents")
    incidents = incidents_resp.get("incidents", [])
    print(f"[+] Total Incidents created: {len(incidents)}")
    assert len(incidents) == 1, f"Expected exactly 1 correlated incident, but got {len(incidents)}!"
    
    incident = incidents[0]
    alerts_in_incident = incident.get("alerts", [])
    print(f"[+] Total Alerts clustered in incident: {len(alerts_in_incident)}")
    assert len(alerts_in_incident) == 4, f"Expected 4 alerts grouped, got {len(alerts_in_incident)}"

    # Step 5: Probable-Cause Ranking & Blast Radius Verification
    print("\n[Step 5] Validating Probable Root Cause & Blast Radius Ranking...")
    root_cause = incident.get("probable_root_cause", {})
    symptoms = incident.get("symptoms", [])
    blast_radius = incident.get("blast_radius", [])
    causal_path = incident.get("causal_path", [])

    print(f"[+] Probable Root Cause: {root_cause.get('service')} ({root_cause.get('alertname')})")
    print(f"[+] Confidence: {root_cause.get('confidence') * 100:.1f}%")
    print(f"[+] Causal Path: {' -> '.join(causal_path)}")
    print(f"[+] Blast Radius ({len(blast_radius)} services): {blast_radius}")
    print(f"[+] Downstream Symptoms ({len(symptoms)}):")
    for s in symptoms:
        print(f"    - {s['service']} ({s['alertname']}): {s['hops_from_root']} hops downstream")

    assert root_cause.get("service") == "chi-argus-clickhouse", f"Expected root cause chi-argus-clickhouse, got {root_cause.get('service')}"
    assert root_cause.get("alertname") == "ClickHouseConnectionPoolExhausted"
    assert root_cause.get("confidence", 0) >= 0.85, f"Confidence {root_cause.get('confidence')} too low"
    assert len(symptoms) == 3, f"Expected 3 symptoms, got {len(symptoms)}"
    assert "argus-sample-service" in blast_radius
    assert "argus-auto-service" in blast_radius
    assert "argus-synthetic-probe" in blast_radius

    # Save probable-cause evidence
    ranking_evidence = {
        "incident_id": incident.get("incident_id"),
        "probable_root_cause": root_cause,
        "symptoms": symptoms,
        "causal_path": causal_path,
        "blast_radius": blast_radius,
        "total_alerts": len(alerts_in_incident)
    }
    with open(os.path.join(EVIDENCE_DIR, "probable-cause-ranking.json"), "w") as f:
        json.dump(ranking_evidence, f, indent=2)
    print(f"[+] Probable-cause ranking saved to {EVIDENCE_DIR}/probable-cause-ranking.json")

    # Step 6: ServiceNow Integration & Single-Page Verification
    print("\n[Step 6] Verifying ServiceNow Incident Dispatch (1 Page for Cascade)...")
    sn_resp = http_json(f"{SERVICENOW_URL}/api/now/table/incident")
    sn_incidents = sn_resp.get("result", [])
    print(f"[+] Total Incidents created in ServiceNow: {len(sn_incidents)}")
    assert len(sn_incidents) == 1, f"Alert storm triggered! Expected 1 ticket in ServiceNow, but found {len(sn_incidents)} tickets!"

    sn_ticket = sn_incidents[0]
    print(f"[+] ServiceNow Ticket: Number={sn_ticket.get('number')}, SysID={sn_ticket.get('sys_id')}")
    print(f"[+] Short Description: {sn_ticket.get('short_description')}")
    assert "[ARGUS CORRELATED]" in sn_ticket.get("short_description", "")
    assert "chi-argus-clickhouse" in sn_ticket.get("short_description", "")
    assert sn_ticket.get("state") == "1", f"Expected state 1 (New), got {sn_ticket.get('state')}"

    with open(os.path.join(EVIDENCE_DIR, "cascading-failure-incident.json"), "w") as f:
        json.dump(sn_ticket, f, indent=2)
    print(f"[+] Grouped incident payload saved to {EVIDENCE_DIR}/cascading-failure-incident.json")

    # Step 7: Incident Resolution Synchronization
    print("\n[Step 7] Testing Cascading Alert Resolution Synchronization...")
    for alert in cascade_alerts:
        res_alert = dict(alert)
        res_alert["status"] = "resolved"
        http_json(f"{CORRELATION_URL}/webhook/alert", method="POST", data=res_alert)

    # Check incident resolution
    inc_after = http_json(f"{CORRELATION_URL}/api/incidents/{incident['incident_id']}")
    print(f"[+] Incident status after resolutions: {inc_after.get('status')}")
    assert inc_after.get("status") == "resolved", f"Expected incident status resolved, got {inc_after.get('status')}"

    # Verify ServiceNow ticket closed
    sn_after = http_json(f"{SERVICENOW_URL}/api/now/table/incident/{sn_ticket['sys_id']}")
    rec_after = sn_after.get("result", {})
    print(f"[+] ServiceNow ticket state after resolution: {rec_after.get('state')}")
    assert rec_after.get("state") == "6", f"Expected ServiceNow state 6 (Resolved), got {rec_after.get('state')}"

    print("\n=================================================================")
    print("STATUS: PASS — Feature F020 Alert Correlation E2E Verified 100% Green!")
    print("=================================================================")

if __name__ == "__main__":
    main()
