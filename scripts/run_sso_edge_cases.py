#!/usr/bin/env python3
"""
Argus Feature F016: Agency SSO & RBAC Edge Cases & Resilience Battery
Verifies:
1. Failed authentication (bad credentials, unknown user, missing credentials).
2. Role with no access (authenticated identity with zero monitoring roles).
3. Token expiration enforcement (expired JWT rejected with HTTP 401).
4. Cryptographic signature tampering and forged claim rejection.
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request

IDP_URL = os.environ.get("IDP_URL", "http://argus-idp.argus-system.svc.cluster.local:8089").rstrip("/")
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://argus-sso-gateway.argus-system.svc.cluster.local:8088").rstrip("/")

def http_get(url: str, headers: dict = None, timeout: int = 10) -> tuple[int, any]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def http_post_json(url: str, payload: dict, headers: dict = None, timeout: int = 10) -> tuple[int, any]:
    all_headers = {"Content-Type": "application/json"}
    if headers:
        all_headers.update(headers)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=all_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(body)
            except Exception:
                return resp.status, body
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

def make_forged_jwt(payload: dict, secret: str = "bogus-attacker-secret") -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": "fake-key"}
    h_b64 = b64url_encode(json.dumps(header).encode("utf-8"))
    p_b64 = b64url_encode(json.dumps(payload).encode("utf-8"))
    msg = f"{h_b64}.{p_b64}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    return f"{h_b64}.{p_b64}.{b64url_encode(sig)}"

def main():
    print("=================================================================")
    print("        ARGUS SSO & RBAC EDGE CASES & RESILIENCE BATTERY         ")
    print("=================================================================")

    passed = 0
    failed = 0

    # -------------------------------------------------------------
    # Edge Case 1: Failed Authentication (Bad Credentials / Unknown User)
    # -------------------------------------------------------------
    print("--> [Edge Case 1/4] Failed Authentication Handling...")
    c1, _ = http_post_json(f"{IDP_URL}/protocol/openid-connect/token", {
        "grant_type": "password",
        "username": "alice.admin@dhs.gov",
        "password": "wrong_password_attack"
    })
    c2, _ = http_post_json(f"{IDP_URL}/protocol/openid-connect/token", {
        "grant_type": "password",
        "username": "nonexistent.intruder@unknown.com",
        "password": "some_password"
    })
    c3, _ = http_get(f"{GATEWAY_URL}/api/v1/rules")  # No credentials provided
    c4, _ = http_post_json(f"{IDP_URL}/protocol/openid-connect/token", {
        "grant_type": "password",
        "username": "alice.admin@dhs.gov",
        "password": ""
    })

    if c1 == 401 and c2 == 401 and c3 == 401 and c4 == 401:
        print("    PASS: Bad password, empty password, unknown user, and missing token safely rejected with HTTP 401.")
        passed += 1
    else:
        print(f"FAIL: Failed auth was not rejected properly: c1={c1}, c2={c2}, c3={c3}, c4={c4}", file=sys.stderr)
        failed += 1

    # -------------------------------------------------------------
    # Edge Case 2: Role with No Access (Unassigned Monitoring Privileges)
    # -------------------------------------------------------------
    print("--> [Edge Case 2/4] Role with No Access (Contractor / General Staff)...")
    code, unassigned_token_resp = http_post_json(f"{IDP_URL}/protocol/openid-connect/token", {
        "grant_type": "password",
        "username": "mallory.unassigned@dhs.gov",
        "password": "unassigned_pass"
    })
    if code != 200:
        print(f"FAIL: IdP failed to issue token for mallory: {code}", file=sys.stderr)
        failed += 1
    else:
        mallory_token = unassigned_token_resp["access_token"]
        # Gateway check
        c_gw, resp_gw = http_get(f"{GATEWAY_URL}/sso/me", headers={"Authorization": f"Bearer {mallory_token}"})
        if c_gw == 403 and "no assigned monitoring roles" in str(resp_gw).lower():
            print("    PASS: Authenticated user without monitoring role strictly denied with HTTP 403 Forbidden.")
            passed += 1
        else:
            print(f"FAIL: Unassigned role was not blocked with 403: {c_gw} {resp_gw}", file=sys.stderr)
            failed += 1

    # -------------------------------------------------------------
    # Edge Case 3: Token Expiry Enforcement
    # -------------------------------------------------------------
    print("--> [Edge Case 3/4] Token Expiration Enforcement...")
    # Request token from IdP with 1 second expiry
    c_exp, exp_token_resp = http_post_json(f"{IDP_URL}/protocol/openid-connect/token", {
        "grant_type": "password",
        "username": "alice.admin@dhs.gov",
        "password": "admin_pass",
        "expires_in": 1
    })
    if c_exp != 200:
        print(f"FAIL: IdP token generation failed: {c_exp}", file=sys.stderr)
        failed += 1
    else:
        exp_token = exp_token_resp["access_token"]
        print("    Awaiting token expiry (sleeping 2s)...")
        time.sleep(2)
        c_ver, resp_ver = http_get(f"{GATEWAY_URL}/sso/me", headers={"Authorization": f"Bearer {exp_token}"})
        if c_ver == 401 and "expired" in str(resp_ver).lower():
            print("    PASS: Expired token strictly rejected with HTTP 401 Unauthorized (Token has expired).")
            passed += 1
        else:
            print(f"FAIL: Expired token accepted or wrong code: {c_ver} {resp_ver}", file=sys.stderr)
            failed += 1

    # -------------------------------------------------------------
    # Edge Case 4: Cryptographic Signature Tampering & Forged Claims
    # -------------------------------------------------------------
    print("--> [Edge Case 4/4] Cryptographic Signature Tampering & Forged Claims...")
    forged_token = make_forged_jwt({
        "sub": "mallory.attacker",
        "email": "mallory.attacker@evil.com",
        "roles": ["Admin"],
        "groups": ["dhs-soc-admins"],
        "exp": int(time.time()) + 3600
    }, secret="bogus-key-signature-mismatch")

    c_tamper, resp_tamper = http_get(f"{GATEWAY_URL}/api/v1/rules", headers={"Authorization": f"Bearer {forged_token}"})
    if c_tamper == 401 and "invalid cryptographic signature" in str(resp_tamper).lower():
        print("    PASS: Forged token with invalid signature rejected with HTTP 401 Unauthorized.")
        passed += 1
    else:
        print(f"FAIL: Forged token was not blocked: {c_tamper} {resp_tamper}", file=sys.stderr)
        failed += 1

    # Summary
    print("=================================================================")
    print(f"SSO Edge Cases: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    print("STATUS: PASS — All SSO and RBAC edge cases verified 100% green.")
    print("=================================================================")

if __name__ == "__main__":
    main()
