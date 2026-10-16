#!/usr/bin/env python3
"""
Argus Feature F013 End-to-End Incident Paging Verification Controller
Validates alert emission -> gateway reception -> ServiceNow incident creation -> alert resolution -> ServiceNow incident resolution.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://argus-paging-gateway.argus-system.svc.cluster.local:9099")
SERVICENOW_URL = os.environ.get("SERVICENOW_URL", "http://argus-servicenow-mock.argus-system.svc.cluster.local:8088")
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "/tmp/evidence-f013")
PAGING_WEBHOOK_TOKEN = os.environ.get("PAGING_WEBHOOK_TOKEN", "")

def http_json(url: str, data: dict = None, method: str = None) -> tuple[int, dict]:
    m = method or ("POST" if data is not None else "GET")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if PAGING_WEBHOOK_TOKEN:
        headers["X-Webhook-Token"] = PAGING_WEBHOOK_TOKEN
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
        headers=headers,
        method=m
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(content)
        except:
            return e.code, {"raw_error": content}

def main():
    print("=================================================================")
    print("       ARGUS PAGING PATH & SERVICENOW INCIDENT PROOF (F013)      ")
    print("=================================================================")

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # 1. Reset state
    print("--> [1/5] Resetting gateway and mock state for clean test...")
    http_json(f"{SERVICENOW_URL}/api/now/table/incident", method="DELETE")
    http_json(f"{GATEWAY_URL}/api/reset", data={})

    # 2. Fire Alert
    fingerprint = f"fp-{int(time.time())}"
    alert_name = "ArgusServiceLatencySLABreach"
    firing_payload = {
        "version": "4",
        "groupKey": f"{alert_name}:argus-sample-service",
        "status": "firing",
        "receiver": "argus-paging-gateway",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": alert_name,
                    "severity": "critical",
                    "service": "argus-sample-service",
                    "namespace": "argus-system",
                    "job": "sample-service"
                },
                "annotations": {
                    "summary": "Sample service p99 latency exceeded 500ms SLA",
                    "description": "Observed 980ms latency across 5m evaluation window.",
                    "runbook_url": "https://wiki.dhs.gov/sre/runbooks/argus-sample-latency"
                },
                "startsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "fingerprint": fingerprint
            }
        ]
    }

    print(f"--> [2/5] Emitting firing alert notification to Paging Gateway ({alert_name}, fp={fingerprint})...")
    status, res = http_json(f"{GATEWAY_URL}/webhook/alert", data=firing_payload)
    if status != 200 or res.get("status") != "success":
        print(f"ERROR: Paging gateway rejected alert: {res}", file=sys.stderr)
        sys.exit(1)
    print(f"    Gateway response: {res.get('processed_count')} alert(s) processed.")

    # 3. Verify ServiceNow Incident Creation
    print("--> [3/5] Querying ServiceNow Table API for generated incident ticket...")
    time.sleep(1)
    status, sn_res = http_json(f"{SERVICENOW_URL}/api/now/table/incident")
    if status != 200:
        print(f"ERROR: Failed to query ServiceNow mock: {sn_res}", file=sys.stderr)
        sys.exit(1)

    incidents = sn_res.get("result", [])
    matched_inc = None
    for inc in incidents:
        if inc.get("correlation_id") == fingerprint:
            matched_inc = inc
            break

    if not matched_inc:
        print(f"ERROR: No ServiceNow incident found with correlation_id {fingerprint}!", file=sys.stderr)
        print(f"ServiceNow incidents found: {incidents}", file=sys.stderr)
        sys.exit(1)

    sys_id = matched_inc["sys_id"]
    number = matched_inc["number"]
    print("    ServiceNow Incident Successfully Created:")
    print(f"      Sys ID:             {sys_id}")
    print(f"      Incident Number:    {number}")
    print(f"      Short Description:  {matched_inc.get('short_description')}")
    print(f"      Urgency:            {matched_inc.get('urgency')} (1 = Critical)")
    print(f"      Impact:             {matched_inc.get('impact')} (1 = Critical)")
    print(f"      State:              {matched_inc.get('state')} (1 = New)")
    print(f"      Assignment Group:   {matched_inc.get('assignment_group')}")

    # Save evidence
    with open(f"{EVIDENCE_DIR}/servicenow-incident-created.json", "w") as f:
        json.dump(matched_inc, f, indent=2)

    # 4. Resolve Alert
    print("--> [4/5] Emitting alert resolution event to Paging Gateway...")
    resolved_payload = {
        "version": "4",
        "groupKey": f"{alert_name}:argus-sample-service",
        "status": "resolved",
        "receiver": "argus-paging-gateway",
        "alerts": [
            {
                "status": "resolved",
                "labels": {
                    "alertname": alert_name,
                    "severity": "critical",
                    "service": "argus-sample-service",
                    "namespace": "argus-system",
                    "job": "sample-service"
                },
                "annotations": {
                    "summary": "Sample service p99 latency returned to normal (120ms)",
                    "description": "Latency recovered."
                },
                "startsAt": firing_payload["alerts"][0]["startsAt"],
                "endsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "fingerprint": fingerprint
            }
        ]
    }

    status, res = http_json(f"{GATEWAY_URL}/webhook/alert", data=resolved_payload)
    if status != 200:
        print(f"ERROR: Paging gateway failed on resolved event: {res}", file=sys.stderr)
        sys.exit(1)

    time.sleep(1)
    status, updated_inc_res = http_json(f"{SERVICENOW_URL}/api/now/table/incident/{sys_id}")
    if status != 200:
        print(f"ERROR: Failed to retrieve updated incident {sys_id}: {updated_inc_res}", file=sys.stderr)
        sys.exit(1)

    updated_inc = updated_inc_res.get("result", {})
    if updated_inc.get("state") != "6":
        print(f"ERROR: Expected incident state 6 (Resolved), found {updated_inc.get('state')}", file=sys.stderr)
        sys.exit(1)

    print("    ServiceNow Incident Successfully Resolved:")
    print(f"      State:              {updated_inc.get('state')} (6 = Resolved)")
    print(f"      Close Notes:        {updated_inc.get('close_notes')}")

    with open(f"{EVIDENCE_DIR}/servicenow-incident-resolved.json", "w") as f:
        json.dump(updated_inc, f, indent=2)

    # 5. Gateway Status & Metrics
    print("--> [5/5] Fetching gateway operational metrics...")
    status, gw_status = http_json(f"{GATEWAY_URL}/api/status")
    with open(f"{EVIDENCE_DIR}/gateway-status.json", "w") as f:
        json.dump(gw_status, f, indent=2)
    print(f"    Gateway stats: {gw_status.get('stats')}")

    print("=================================================================")
    print("   FEATURE F013 INCIDENT PAGING & SERVICENOW VERIFIED GREEN!     ")
    print("=================================================================")

if __name__ == "__main__":
    main()
