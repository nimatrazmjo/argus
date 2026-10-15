#!/usr/bin/env python3
"""
deploy/alerting/sync_rules.py — High-performance declarative rule sync controller
Runs inside cluster with direct access to SigNoz API.
"""
import urllib.request
import urllib.error
import urllib.parse
import json
import sys
import os

ADMIN_EMAIL = os.environ.get("SIGNOZ_ADMIN_EMAIL", "admin@argus.internal")
ADMIN_PASSWORD = os.environ.get("SIGNOZ_ADMIN_PASSWORD", "ArgusAdminPassword123!")
SIGNOZ_HOST = os.environ.get("SIGNOZ_HOST", "http://signoz.argus-system.svc.cluster.local:8080")
RULES_PATH = os.environ.get("RULES_PATH", "/tmp/alerting/rules.json")

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
    print("=" * 65)
    print("       ARGUS DECLARATIVE ALERT RULES SYNC CONTROLLER (PYTHON)   ")
    print("=" * 65)

    if "RULES_JSON_STRING" in os.environ and os.environ["RULES_JSON_STRING"].strip():
        rules_doc = json.loads(os.environ["RULES_JSON_STRING"])
        print("--> Loaded declarative rule definitions from RULES_JSON_STRING env var")
    elif os.path.exists(RULES_PATH):
        with open(RULES_PATH, "r") as f:
            rules_doc = json.load(f)
        print(f"--> Loaded declarative rule definitions from {RULES_PATH}")
    elif len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        with open(sys.argv[1], "r") as f:
            rules_doc = json.load(f)
        print(f"--> Loaded declarative rule definitions from {sys.argv[1]}")
    else:
        print(f"ERROR: No rules definition found in env var or {RULES_PATH}", file=sys.stderr)
        sys.exit(1)
    rules_list = rules_doc.get("rules", [])

    # 1. Fetch Org ID
    print("--> Authenticating with SigNoz API...")
    context_url = f"{SIGNOZ_HOST}/api/v2/sessions/context?email={urllib.parse.quote(ADMIN_EMAIL)}"
    ctx_resp = request(context_url)
    orgs = ctx_resp.get("data", {}).get("orgs", [])
    if not orgs:
        print("ERROR: No orgs found in session context", file=sys.stderr)
        sys.exit(1)
    org_id = orgs[0]["id"]

    # 2. Login
    login_url = f"{SIGNOZ_HOST}/api/v2/sessions/email_password"
    login_payload = {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "orgId": org_id}
    login_resp = request(login_url, method="POST", data=login_payload)
    token = login_resp.get("data", {}).get("accessToken")
    if not token:
        print("ERROR: Failed to acquire access token", file=sys.stderr)
        sys.exit(1)
    print(f"    Authenticated as {ADMIN_EMAIL} (Org ID: {org_id})")

    # 2.5 Ensure default notification channel exists
    print("--> Checking notification channels...")
    channels_url = f"{SIGNOZ_HOST}/api/v1/channels"
    channels_resp = request(channels_url, token=token)
    channels_list = channels_resp.get("data", [])
    channel_names = {c.get("name") for c in channels_list if "name" in c}
    if "argus-default-webhook" not in channel_names:
        print("    Creating default notification channel [argus-default-webhook]...")
        channel_payload = {
            "name": "argus-default-webhook",
            "webhook_configs": [
                {
                    "send_resolved": True,
                    "url": "http://argus-sample-service.argus-system.svc.cluster.local:8080/api/alerts"
                }
            ]
        }
        request(channels_url, method="POST", data=channel_payload, token=token)
        print("    -> Default notification channel created successfully.")
    else:
        print("    Default notification channel [argus-default-webhook] is active.")

    # 3. Fetch existing rules via v2 API
    rules_url = f"{SIGNOZ_HOST}/api/v2/rules"
    existing_resp = request(rules_url, token=token)
    data_field = existing_resp.get("data", [])
    existing_rules = data_field if isinstance(data_field, list) else data_field.get("rules", [])
    existing_by_name = {r.get("alert"): r for r in existing_rules if "alert" in r}
    print(f"--> Found {len(existing_rules)} existing rules in SigNoz engine")

    # 4. Synchronize rules idempotently
    print("--> Synchronizing declarative alert rules...")
    synced_ids = []
    for rule in rules_list:
        alert_name = rule["alert"]
        if alert_name in existing_by_name:
            existing_id = existing_by_name[alert_name]["id"]
            print(f"    Updating existing rule [{alert_name}] (ID: {existing_id})...")
            update_url = f"{SIGNOZ_HOST}/api/v2/rules/{existing_id}"
            request(update_url, method="PUT", data=rule, token=token, timeout=60)
            print(f"      -> Successfully updated [{alert_name}]")
            synced_ids.append(existing_id)
        else:
            print(f"    Creating new rule [{alert_name}]...")
            create_resp = request(rules_url, method="POST", data=rule, token=token, timeout=60)
            new_id = create_resp.get("data", {}).get("id")
            print(f"      -> Successfully created [{alert_name}] (ID: {new_id})")
            synced_ids.append(new_id)

    print("=" * 65)
    print(f"SUCCESS: Synchronized {len(synced_ids)} rules into SigNoz engine.")
    print("=" * 65)

if __name__ == "__main__":
    main()
