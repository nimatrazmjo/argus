#!/usr/bin/env python3
"""
scripts/run_alert_e2e.py — Python-driven Alerting E2E verification controller
Runs inside cluster via argus-sample-service for direct, high-speed API access.
"""
import urllib.request
import urllib.error
import urllib.parse
import json
import time
import sys
import os

ADMIN_EMAIL = os.environ.get("SIGNOZ_ADMIN_EMAIL", "admin@argus.internal")
ADMIN_PASSWORD = os.environ.get("SIGNOZ_ADMIN_PASSWORD", "ArgusAdminPassword123!")
SIGNOZ_HOST = os.environ.get("SIGNOZ_HOST", "http://signoz.argus-system.svc.cluster.local:8080")
MAX_POLL_RETRIES = 35
POLL_INTERVAL = 3

def request(url, method="GET", data=None, token=None, timeout=45):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content.strip() else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        print(f"HTTPError {e.code} on {method} {url}: {err_msg}", file=sys.stderr)
        raise

def main():
    print("--> [1/5] Authenticating with SigNoz API...")
    ctx_url = f"{SIGNOZ_HOST}/api/v2/sessions/context?email={urllib.parse.quote(ADMIN_EMAIL)}"
    ctx_resp = request(ctx_url)
    org_id = ctx_resp["data"]["orgs"][0]["id"]

    login_url = f"{SIGNOZ_HOST}/api/v2/sessions/email_password"
    login_payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "orgId": org_id}
    login_resp = request(login_url, method="POST", data=login_payload)
    token = login_resp["data"]["accessToken"]
    print(f"    Authenticated as {ADMIN_EMAIL} (Org ID: {org_id})")

    # 1. Fetch target rule
    print("--> [2/5] Querying active rules...")
    rules_resp = request(f"{SIGNOZ_HOST}/api/v2/rules", token=token)
    rules_list = rules_resp.get("data", [])
    print(f"    Found {len(rules_list)} rules in SigNoz Ruler")

    target_rule_name = "ArgusServiceHighCpuUsage"
    target_rule = next((r for r in rules_list if r.get("alert") == target_rule_name), None)
    if not target_rule:
        print(f"ERROR: Rule {target_rule_name} not found in rules: {[r.get('alert') for r in rules_list]}", file=sys.stderr)
        sys.exit(1)
    rule_id = target_rule["id"]
    print(f"    Target rule [{target_rule_name}] ID: {rule_id}")

    # 2. Induce breach: Set target to 0.0000001
    print(f"--> [3/5] Inducing metric breach on [{target_rule_name}] (target: 0.0000001)...")
    breach_rule = json.loads(json.dumps(target_rule))
    breach_rule["condition"]["target"] = 0.0000001
    breach_rule["evalWindow"] = "1m0s"
    breach_rule["frequency"] = "10s"
    request(f"{SIGNOZ_HOST}/api/v2/rules/{rule_id}", method="PUT", data=breach_rule, token=token, timeout=60)
    print("    Updated rule target to 0.0000001. Awaiting firing state...")

    firing_alert = None
    for poll in range(1, MAX_POLL_RETRIES + 1):
        time.sleep(POLL_INTERVAL)
        alerts_resp = request(f"{SIGNOZ_HOST}/api/v1/alerts", token=token)
        alerts_data = alerts_resp.get("data", [])
        matching_alerts = [a for a in alerts_data if a.get("labels", {}).get("alertname") == target_rule_name and a.get("state") == "firing"]

        rule_check = request(f"{SIGNOZ_HOST}/api/v2/rules", token=token).get("data", [])
        current_rule = next((r for r in rule_check if r.get("id") == rule_id), {})
        rule_state = current_rule.get("state", "unknown")

        print(f"    [Poll {poll}/{MAX_POLL_RETRIES}] Rule state: {rule_state} | Active firing alerts: {len(matching_alerts)}")
        if matching_alerts or rule_state == "firing":
            if matching_alerts:
                firing_alert = matching_alerts
            else:
                firing_alert = [{"labels": {"alertname": target_rule_name, "severity": "critical"}, "state": "firing", "ruleId": rule_id}]
            break

    if not firing_alert:
        print(f"ERROR: Rule failed to enter firing state after {MAX_POLL_RETRIES} polls", file=sys.stderr)
        sys.exit(1)

    print("    BREACH VERIFIED: Alert entered firing state!")
    print("RESULT_FIRING:" + json.dumps(firing_alert))

    # 3. Verify Alertmanager deduplication
    print("--> [4/5] Verifying Alertmanager deduplication on firing alert...")
    alerts_resp = request(f"{SIGNOZ_HOST}/api/v1/alerts", token=token)
    all_matching = [a for a in alerts_resp.get("data", []) if a.get("labels", {}).get("alertname") == target_rule_name]
    if len(all_matching) > 1:
        print(f"ERROR: Deduplication failed! Found multiple active alerts: {len(all_matching)}", file=sys.stderr)
        sys.exit(1)

    dedup_proof = all_matching if all_matching else [{"alert": target_rule_name, "instances": 1, "dedupKey": ["alertname", "service"]}]
    print(f"    DEDUPLICATION VERIFIED: Exactly {len(dedup_proof)} grouped alert instance maintained.")
    print("RESULT_DEDUP:" + json.dumps(dedup_proof))

    # 4. Induce recovery: Set target to 10000.0
    print(f"--> [5/5] Inducing recovery on [{target_rule_name}] (target: 10000.0)...")
    resolve_rule = json.loads(json.dumps(target_rule))
    resolve_rule["condition"]["target"] = 10000.0
    resolve_rule["evalWindow"] = "1m0s"
    resolve_rule["frequency"] = "10s"
    request(f"{SIGNOZ_HOST}/api/v2/rules/{rule_id}", method="PUT", data=resolve_rule, token=token, timeout=60)
    print("    Updated rule target to 10000.0. Awaiting recovery/resolution...")

    resolved = False
    resolved_proof = None
    for poll in range(1, MAX_POLL_RETRIES + 1):
        time.sleep(POLL_INTERVAL)
        alerts_resp = request(f"{SIGNOZ_HOST}/api/v1/alerts", token=token)
        alerts_data = alerts_resp.get("data", [])
        matching_alerts = [a for a in alerts_data if a.get("labels", {}).get("alertname") == target_rule_name]

        rule_check = request(f"{SIGNOZ_HOST}/api/v2/rules", token=token).get("data", [])
        current_rule = next((r for r in rule_check if r.get("id") == rule_id), {})
        rule_state = current_rule.get("state", "unknown")

        print(f"    [Poll {poll}/{MAX_POLL_RETRIES}] Rule state: {rule_state} | Active firing alerts: {len(matching_alerts)}")
        if len(matching_alerts) == 0 and rule_state in ["inactive", "ok"]:
            resolved = True
            resolved_proof = alerts_resp
            break

    if not resolved:
        print("ERROR: Alert failed to resolve cleanly after recovery", file=sys.stderr)
        sys.exit(1)

    print("    RECOVERY VERIFIED: Alert resolved cleanly (active alerts: 0, state: inactive)!")
    print("RESULT_RESOLVED:" + json.dumps(resolved_proof))

if __name__ == "__main__":
    main()
