#!/usr/bin/env bash
# deploy/slo/apply-slo.sh — Synchronizes declarative SLO alert rules with SigNoz Ruler
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RULES_FILE="${SCRIPT_DIR}/slo-rules.json"
NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
ADMIN_EMAIL="${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
ADMIN_PASSWORD="${SIGNOZ_ADMIN_PASSWORD:-ArgusAdminPassword123!}"

echo "================================================================="
echo "       ARGUS SLO DECLARATIVE ALERT RULES SYNC CONTROLLER         "
echo "================================================================="

if [ ! -f "${RULES_FILE}" ]; then
  echo "ERROR: SLO rules definition file not found: ${RULES_FILE}" >&2
  exit 1
fi

echo "--> [1/2] Reading declarative SLO rule manifests from ${RULES_FILE}..."
RULE_COUNT=$(jq '.rules | length' "${RULES_FILE}")
echo "    Found ${RULE_COUNT} SLO rule definitions in ${RULES_FILE}"

echo "--> [2/2] Synchronizing SLO rules to SigNoz Ruler engine via cluster..."
RULES_B64=$(base64 < "${RULES_FILE}" | tr -d '\n')

kubectl exec </dev/null -n "${NAMESPACE}" deployment/argus-sample-service -- python -c "
import urllib.request, urllib.error, urllib.parse, json, sys, base64

ADMIN_EMAIL = '${ADMIN_EMAIL}'
ADMIN_PASSWORD = '${ADMIN_PASSWORD}'
SIGNOZ_HOST = 'http://signoz.argus-system.svc.cluster.local:8080'
RULES_RAW = base64.b64decode('${RULES_B64}').decode('utf-8')
RULES_DOC = json.loads(RULES_RAW)
RULES = RULES_DOC.get('rules', [])

# 1. Fetch Org ID
req = urllib.request.Request(f'{SIGNOZ_HOST}/api/v2/sessions/context?email={urllib.parse.quote(ADMIN_EMAIL)}')
with urllib.request.urlopen(req, timeout=30) as resp:
    org_id = json.loads(resp.read().decode())['data']['orgs'][0]['id']

# 2. Login
payload = json.dumps({'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD, 'orgId': org_id}).encode()
req = urllib.request.Request(f'{SIGNOZ_HOST}/api/v2/sessions/email_password', data=payload, headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(req, timeout=30) as resp:
    token = json.loads(resp.read().decode())['data']['accessToken']
print(f'    Authenticated with SigNoz API as {ADMIN_EMAIL} (Org ID: {org_id})')

# 3. Query existing rules via /api/v2/rules
req = urllib.request.Request(f'{SIGNOZ_HOST}/api/v2/rules', headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req, timeout=30) as resp:
    existing_rules = json.loads(resp.read().decode()).get('data', [])
existing_by_name = {r['alert']: r for r in existing_rules if 'alert' in r}
print(f'    Found {len(existing_rules)} active rules in engine before sync')

# 4. Synchronize rules
synced = []
for rule in RULES:
    alert_name = rule['alert']
    rule_bytes = json.dumps(rule).encode('utf-8')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    try:
        if alert_name in existing_by_name:
            rule_id = existing_by_name[alert_name]['id']
            req = urllib.request.Request(f'{SIGNOZ_HOST}/api/v2/rules/{rule_id}', data=rule_bytes, headers=headers, method='PUT')
            with urllib.request.urlopen(req, timeout=60) as resp:
                print(f'    -> Updated existing SLO rule [{alert_name}] (ID: {rule_id})')
            synced.append(rule_id)
        else:
            req = urllib.request.Request(f'{SIGNOZ_HOST}/api/v2/rules', data=rule_bytes, headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=60) as resp:
                content = resp.read().decode()
                new_id = json.loads(content)['data']['id'] if content.strip() else 'ok'
                print(f'    -> Created new SLO rule [{alert_name}] (ID: {new_id})')
            synced.append(new_id)
    except urllib.error.HTTPError as e:
        print(f'ERROR on SLO rule [{alert_name}]: {e.code} - {e.read().decode()}', file=sys.stderr)
        raise

print(f'    Successfully synchronized {len(synced)} SLO rules into SigNoz engine.')
"

echo "================================================================="
echo "   SLO RULES SYNCHRONIZATION COMPLETED SUCCESSFULLY!             "
echo "================================================================="
