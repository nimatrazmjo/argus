#!/usr/bin/env bash
# deploy/signoz/register-admin.sh — one-time SigNoz admin/org bootstrap (idempotent)
# Needs SIGNOZ_ADMIN_PASSWORD (>=12 chars, upper/lower/digit/symbol). Skips if setup already done.
set -euo pipefail

NAMESPACE="${ARGUS_NAMESPACE:-argus-system}"
ADMIN_EMAIL="${SIGNOZ_ADMIN_EMAIL:-admin@argus.internal}"
ADMIN_NAME="${SIGNOZ_ADMIN_NAME:-admin}"
ORG_NAME="${SIGNOZ_ORG_NAME:-argus}"

if [ -z "${SIGNOZ_ADMIN_PASSWORD:-}" ]; then
  echo "    SIGNOZ_ADMIN_PASSWORD not set; skipping SigNoz admin registration."
  echo "    Register in the UI, or re-run with SIGNOZ_ADMIN_PASSWORD set."
  exit 0
fi

# Credentials go via stdin, not argv, so they don't show in process lists.
printf '%s' "${SIGNOZ_ADMIN_PASSWORD}" | kubectl exec -i -n "${NAMESPACE}" deployment/argus-sso-gateway -- python -c "
import sys, json, time, urllib.request, urllib.error
host = 'http://signoz.${NAMESPACE}.svc.cluster.local:8080'
password = sys.stdin.read()

def call(path, data=None):
    req = urllib.request.Request(host + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

for _ in range(30):                      # wait for SigNoz API
    try:
        version = call('/api/v1/version'); break
    except Exception:
        time.sleep(5)
else:
    sys.exit('ERROR: SigNoz API not reachable')

if version.get('setupCompleted'):
    print('    SigNoz already set up; skipping admin registration.')
    sys.exit(0)

body = json.dumps({'name': '${ADMIN_NAME}', 'orgName': '${ORG_NAME}',
                   'email': '${ADMIN_EMAIL}', 'password': password}).encode()
try:
    call('/api/v1/register', body)
except urllib.error.HTTPError as e:
    sys.exit('ERROR: register failed: %d %s' % (e.code, e.read().decode()[:300]))
print('    Registered SigNoz admin ${ADMIN_EMAIL} (org ${ORG_NAME}).')
"
