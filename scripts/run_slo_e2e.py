#!/usr/bin/env python3
"""
scripts/run_slo_e2e.py — End-to-End Service Level Objective (SLO) Verification Controller
Executes traffic simulation, SLI accounting validation, error budget burndown,
and dashboard rendering assertions inside the Argus Kubernetes cluster.
"""

import urllib.request
import urllib.parse
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8080"
SIGNOZ_URL = "http://signoz.argus-system.svc.cluster.local:8080"
ADMIN_EMAIL = "admin@argus.internal"
ADMIN_PASSWORD = "ArgusAdminPassword123!"


def http_get(url, timeout=30):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8"), resp.status


def http_post(url, data=None, headers=None, timeout=30):
    headers = headers or {}
    body = json.dumps(data).encode("utf-8") if data is not None else b""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8"), resp.status


def signoz_auth():
    ctx_url = f"{SIGNOZ_URL}/api/v2/sessions/context?email={urllib.parse.quote(ADMIN_EMAIL)}"
    ctx_body, _ = http_get(ctx_url)
    org_id = json.loads(ctx_body)["data"]["orgs"][0]["id"]

    login_url = f"{SIGNOZ_URL}/api/v2/sessions/email_password"
    login_data = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "orgId": org_id}
    login_body, _ = http_post(login_url, data=login_data, headers={"Content-Type": "application/json"})
    token = json.loads(login_body)["data"]["accessToken"]
    return token


def main():
    print("--> [1/6] Resetting SLO tracker to clean baseline...")
    reset_resp, status = http_post(f"{BASE_URL}/api/slo/reset")
    if status != 200:
        print(f"ERROR: SLO reset returned HTTP {status}", file=sys.stderr)
        sys.exit(1)
    reset_data = json.loads(reset_resp)
    print(f"    SLO Tracker reset confirmed: {reset_data['slo']['status']} (total: {reset_data['slo']['total_requests']})")

    # Step 2: Seed 100 successful requests
    print("--> [2/6] Seeding 100 successful requests (target: 99.0% SLO)...")
    for i in range(100):
        url = f"{BASE_URL}/order?order_id=seed-{i:03d}"
        http_get(url)
        time.sleep(0.01)

    baseline_resp, _ = http_get(f"{BASE_URL}/api/slo")
    baseline = json.loads(baseline_resp)
    print(f"    Baseline SLI: {baseline['sli_percent']}% | Budget Remaining: {baseline['error_budget_remaining_percent']}% | Status: {baseline['status']}")

    if baseline["total_requests"] < 100:
        print(f"ERROR: Expected at least 100 requests, got {baseline['total_requests']}", file=sys.stderr)
        sys.exit(1)
    if baseline["sli_percent"] != 100.0:
        print(f"ERROR: Expected 100.0% SLI, got {baseline['sli_percent']}", file=sys.stderr)
        sys.exit(1)
    if baseline["error_budget_remaining_percent"] != 100.0:
        print(f"ERROR: Expected 100.0% budget remaining, got {baseline['error_budget_remaining_percent']}", file=sys.stderr)
        sys.exit(1)
    if baseline["burn_rate"] != 0.0:
        print(f"ERROR: Expected 0.0 burn rate, got {baseline['burn_rate']}", file=sys.stderr)
        sys.exit(1)

    print("SLO_BASELINE:" + json.dumps(baseline))

    # Step 3: Induce Error Traffic to Burn Error Budget
    print("--> [3/6] Inducing controlled errors to burn error budget...")
    # Send 5 errors with total requests = 105
    for i in range(5):
        try:
            http_get(f"{BASE_URL}/order?fail=true&order_id=err-{i:02d}")
        except urllib.error.HTTPError as e:
            if e.code != 500:
                print(f"WARN: Unexpected HTTP error code {e.code}", file=sys.stderr)

    burned_resp, _ = http_get(f"{BASE_URL}/api/slo")
    burned = json.loads(burned_resp)
    print(f"    Burned SLI: {burned['sli_percent']}% | Budget Consumed: {burned['error_budget_consumed_percent']}% | Remaining: {burned['error_budget_remaining_percent']}% | Burn Rate: {burned['burn_rate']}x | Status: {burned['status']}")

    if burned["bad_requests"] != 5:
        print(f"ERROR: Expected 5 bad requests, got {burned['bad_requests']}", file=sys.stderr)
        sys.exit(1)
    if burned["sli_percent"] >= 99.0:
        print(f"ERROR: Expected SLI < 99.0%, got {burned['sli_percent']}", file=sys.stderr)
        sys.exit(1)
    if burned["error_budget_consumed_percent"] <= 0.0:
        print(f"ERROR: Expected budget consumed > 0.0%, got {burned['error_budget_consumed_percent']}", file=sys.stderr)
        sys.exit(1)
    if burned["burn_rate"] <= 0.0:
        print(f"ERROR: Expected positive burn rate, got {burned['burn_rate']}", file=sys.stderr)
        sys.exit(1)

    print("SLO_BURNED:" + json.dumps(burned))

    # Step 4: Verify HTML Dashboard rendering
    print("--> [4/6] Verifying visual SLO HTML dashboard (/slo)...")
    html_content, html_status = http_get(f"{BASE_URL}/slo")
    if html_status != 200:
        print(f"ERROR: /slo returned HTTP {html_status}", file=sys.stderr)
        sys.exit(1)

    required_html_fragments = [
        "Argus // SLO & Error Budget Tracker",
        "Service Level Objective (SLO)",
        "Error Budget Burndown",
        "budget-progress-bar",
        "details-table",
        "Current Availability SLI",
        "Error Budget Remaining",
        "Current Burn Rate"
    ]
    for fragment in required_html_fragments:
        if fragment not in html_content:
            print(f"ERROR: HTML dashboard missing expected fragment: '{fragment}'", file=sys.stderr)
            sys.exit(1)

    print("    HTML Dashboard verified successfully (contains all required telemetry & visual widgets).")
    print("SLO_HTML_DASHBOARD:" + json.dumps({"length": len(html_content), "content": html_content}))

    # Step 5: Query SigNoz for synchronized SLO Alert Rules
    print("--> [5/6] Querying SigNoz Ruler for active SLO alert monitors...")
    token = signoz_auth()
    req = urllib.request.Request(f"{SIGNOZ_URL}/api/v2/rules", headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        all_rules = json.loads(resp.read().decode("utf-8")).get("data", [])

    slo_rule_names = ["ArgusSLOFastBurnRate", "ArgusSLOSlowBurnRate", "ArgusSLOBudgetExhausted", "ArgusSLIAvailabilityBreach"]
    synced_slo_rules = [r for r in all_rules if r.get("alert") in slo_rule_names]

    print(f"    Found {len(synced_slo_rules)} / {len(slo_rule_names)} SLO alert monitors in SigNoz Ruler:")
    for r in synced_slo_rules:
        print(f"    - [{r.get('alert')}] Target: {r.get('condition', {}).get('target')} (Severity: {r.get('labels', {}).get('severity')})")

    if len(synced_slo_rules) < len(slo_rule_names):
        print(f"ERROR: Missing expected SLO rules in SigNoz Ruler! Found: {[r.get('alert') for r in synced_slo_rules]}", file=sys.stderr)
        sys.exit(1)

    print("SLO_RULES_SYNCED:" + json.dumps(synced_slo_rules))

    print("--> [6/6] End-to-end SLO tracking & error budget burndown verified 100% green!")


if __name__ == "__main__":
    main()
