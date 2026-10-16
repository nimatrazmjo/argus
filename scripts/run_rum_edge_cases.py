#!/usr/bin/env python3
"""
Argus Feature F017: Real User Monitoring (RUM) & Session Replay Edge Cases Battery
Verifies:
1. Masking correctness across all sensitive formats (PAN, SSN, tokens, emails, passwords) & XSS neutralization.
2. Large session payload handling (1,000+ DOM events & large mutation trees).
3. Replay rendering resilience with missing / 404 external assets and broken stylesheets.
4. Malformed payload rejection, unauthenticated ingest rejection (401), and input validation guardrails.
"""

import json
import os
import secrets
import sys
import time
import urllib.parse
import urllib.request

RUM_URL = os.environ.get("RUM_URL", "http://argus-rum-collector.argus-system.svc.cluster.local:8082")
RUM_INGEST_TOKEN = os.environ.get("RUM_INGEST_TOKEN", "")

def _auth_headers(extra: dict = None, include_auth: bool = True) -> dict:
    hdrs = {}
    if include_auth and RUM_INGEST_TOKEN:
        hdrs["X-RUM-Ingest-Token"] = RUM_INGEST_TOKEN
    if extra:
        hdrs.update(extra)
    return hdrs

def http_get(url: str, timeout: int = 10, include_auth: bool = True) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=_auth_headers(include_auth=include_auth))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

def http_post_json(url: str, payload: any, timeout: int = 10, include_auth: bool = True) -> tuple[int, any]:
    if isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=_auth_headers({"Content-Type": "application/json"}, include_auth=include_auth))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, {"error": body}

def main():
    print("=================================================================")
    print("      ARGUS RUM & SESSION REPLAY EDGE CASES & RESILIENCE BATTERY ")
    print("=================================================================")

    passed = 0
    failed = 0

    # -------------------------------------------------------------
    # Edge Case 1: Masking Correctness & Multi-Pattern Redaction
    # -------------------------------------------------------------
    print("--> [Edge Case 1/4] Masking Correctness & Multi-Pattern Redaction...")
    s1 = f"sess-mask-test-{secrets.token_hex(4)}"
    test_email = "employee.secret@defense-agency.gov"
    test_card1 = "4111 2222 3333 4444"
    test_card2 = "5500-0000-1111-2222"
    test_ssn = "987-65-4321"
    test_bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake_token_data"
    test_pwd = "TopSecretPassword!999"
    safe_product = "Argus Quantum Sensor Unit"
    safe_qty = "10"

    leak_payload = {
        "sessionId": s1,
        "userId": "user-redaction-test",
        "userEmail": test_email,
        "pageUrl": "/account/security",
        "events": [
            {
                "eventId": "evt-1",
                "timestamp": "2026-10-15T20:00:00.000Z",
                "type": "input",
                "targetId": "password",
                "targetSelector": "#password",
                "maskedValue": "***",
                "payload": {"field": "password", "value": test_pwd}
            },
            {
                "eventId": "evt-2",
                "timestamp": "2026-10-15T20:00:01.000Z",
                "type": "input",
                "targetId": "credit_card",
                "targetSelector": "#cc-field",
                "maskedValue": "***",
                "payload": {"card1": test_card1, "card2": test_card2}
            },
            {
                "eventId": "evt-3",
                "timestamp": "2026-10-15T20:00:02.000Z",
                "type": "input",
                "targetId": "ssn",
                "targetSelector": "#ssn-field",
                "maskedValue": "***",
                "payload": {"tax_id": test_ssn}
            },
            {
                "eventId": "evt-4",
                "timestamp": "2026-10-15T20:00:03.000Z",
                "type": "custom",
                "payload": {"auth_header": test_bearer}
            },
            {
                "eventId": "evt-5",
                "timestamp": "2026-10-15T20:00:04.000Z",
                "type": "input",
                "targetId": "product_name",
                "targetSelector": "#product",
                "maskedValue": safe_product,
                "payload": {"product": safe_product, "qty": safe_qty}
            }
        ]
    }

    code, resp = http_post_json(f"{RUM_URL}/v1/rum/ingest", leak_payload)
    if code != 200:
        print(f"FAIL: Ingestion rejected mask-test payload: {code} {resp}", file=sys.stderr)
        failed += 1
    else:
        # Retrieve replay timeline
        r_code, replay_json_str = http_get(f"{RUM_URL}/v1/rum/replay/{s1}")
        replay_obj = json.loads(replay_json_str)
        replay_raw = json.dumps(replay_obj)

        leaks = []
        if test_email in replay_raw: leaks.append("email")
        if test_card1 in replay_raw: leaks.append("card1")
        if test_card2 in replay_raw: leaks.append("card2")
        if test_ssn in replay_raw: leaks.append("ssn")
        if test_bearer in replay_raw: leaks.append("bearer")
        if test_pwd in replay_raw: leaks.append("password")

        safe_intact = safe_product in replay_raw and safe_qty in replay_raw

        if not leaks and safe_intact:
            print("    PASS: All 6 sensitive patterns strictly redacted; safe business attributes preserved!")
            passed += 1
        else:
            print(f"FAIL: PII leaks detected: {leaks}, safe_intact={safe_intact}", file=sys.stderr)
            failed += 1

    # -------------------------------------------------------------
    # Edge Case 2: Large Session Ingestion (1,000+ Events)
    # -------------------------------------------------------------
    print("--> [Edge Case 2/4] Large Session Ingestion & Mutation Stress Test (1,200 events)...")
    s2 = f"sess-large-{secrets.token_hex(4)}"
    large_events = []
    base_time = time.time()

    # Generate 1,200 synthetic DOM mutation & mouse events
    for i in range(1200):
        t_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(base_time + (i * 0.05)))
        large_events.append({
            "eventId": f"evt-large-{i}",
            "timestamp": t_iso,
            "type": "dom_mutation" if i % 2 == 0 else "mousemove",
            "targetSelector": f"#node-{i % 50}",
            "payload": {
                "mutationIndex": i,
                "nodeTree": f"<div class='node' data-index='{i}'><span>Content for mutation {i}</span></div>"
            }
        })

    large_payload = {
        "sessionId": s2,
        "userId": "user-stress-tester",
        "pageUrl": "/catalog/infinite-scroll",
        "events": large_events
    }

    t0 = time.time()
    code, resp = http_post_json(f"{RUM_URL}/v1/rum/ingest", large_payload)
    duration_s = time.time() - t0

    if code == 200 and resp.get("eventsProcessed") == 1200:
        print(f"    PASS: Large session of 1,200 events processed in {duration_s:.3f}s without error or memory exhaustion.")
        passed += 1
    else:
        print(f"FAIL: Large session failed (HTTP {code}): {resp}", file=sys.stderr)
        failed += 1

    # -------------------------------------------------------------
    # Edge Case 3: Replay Resilience with Missing / Broken Assets & Stored XSS Defense
    # -------------------------------------------------------------
    print("--> [Edge Case 3/4] Replay Player Resilience with Missing / 404 External Assets & XSS Neutralization...")
    s3 = f"sess-missing-assets-{secrets.token_hex(4)}"
    broken_html_snapshot = (
        "<html><head>"
        "<link rel='stylesheet' href='https://invalid-nonexistent-cdn.internal/style.css'>"
        "<script src='http://127.0.0.1:9999/broken.js'></script>"
        "</head><body>"
        "<img src='https://missing-image-host.invalid/broken.png' onerror='alert(1)' alt='missing'/>"
        "<h1>Page with Broken Links</h1>"
        "<p>This page should replay cleanly despite missing resources.</p>"
        "</script><script>alert('xss-breakout')</script>"
        "</body></html>"
    )

    missing_asset_payload = {
        "sessionId": s3,
        "userId": "user-broken-assets",
        "pageUrl": "/broken-page",
        "events": [
            {
                "eventId": "evt-broken-snap",
                "timestamp": "2026-10-15T20:05:00.000Z",
                "type": "dom_snapshot",
                "payload": {"snapshot": {"bodyHtml": broken_html_snapshot}}
            },
            {
                "eventId": "evt-broken-err",
                "timestamp": "2026-10-15T20:05:01.000Z",
                "type": "console_error",
                "payload": {"message": "Failed to load resource: net::ERR_NAME_NOT_RESOLVED"}
            }
        ]
    }

    http_post_json(f"{RUM_URL}/v1/rum/ingest", missing_asset_payload)
    p_code, player_html = http_get(f"{RUM_URL}/v1/rum/player/{s3}")

    xss_blocked = "alert('xss-breakout')" not in player_html and "onerror=" not in player_html
    if p_code == 200 and "DOM State Replay Viewport" in player_html and "net::ERR_NAME_NOT_RESOLVED" in player_html and xss_blocked:
        print("    PASS: Replay player safely sandboxes broken assets, strips XSS payloads, and renders gracefully.")
        passed += 1
    else:
        print(f"FAIL: Missing assets or XSS check failed (HTTP {p_code}, xss_blocked={xss_blocked})", file=sys.stderr)
        failed += 1

    # -------------------------------------------------------------
    # Edge Case 4: Malformed Payload, Unauthenticated Ingest & Input Validation Guardrails
    # -------------------------------------------------------------
    print("--> [Edge Case 4/4] Malformed Payload, Unauthenticated Ingest & Schema Input Validation Guardrails...")
    # 4a. Unauthenticated ingest rejected with 401
    c_unauth, _ = http_post_json(f"{RUM_URL}/v1/rum/ingest", {"sessionId": "sess-unauth", "events": []}, include_auth=False)
    # 4b. Empty body
    c1, _ = http_post_json(f"{RUM_URL}/v1/rum/ingest", "")
    # 4c. Invalid JSON syntax
    c2, _ = http_post_json(f"{RUM_URL}/v1/rum/ingest", "{\"sessionId\": broken-json")
    # 4d. Missing sessionId
    c3, _ = http_post_json(f"{RUM_URL}/v1/rum/ingest", {"events": []})
    # 4e. Array instead of object
    c4, _ = http_post_json(f"{RUM_URL}/v1/rum/ingest", ["not-an-object"])

    # 4f. Liveness check post attacks
    c_live, live_resp = http_get(f"{RUM_URL}/healthz", include_auth=False)

    if c_unauth == 401 and c1 == 400 and c2 == 400 and c3 == 400 and c4 == 400 and c_live == 200:
        print("    PASS: Unauthenticated ingest rejected (HTTP 401), malformed payloads rejected (4x HTTP 400); collector liveness intact (HTTP 200).")
        passed += 1
    else:
        print(f"FAIL: Input validation failed: c_unauth={c_unauth}, c1={c1}, c2={c2}, c3={c3}, c4={c4}, c_live={c_live}", file=sys.stderr)
        failed += 1

    # Summary
    print("=================================================================")
    print(f"RUM Edge Cases: {passed} passed, {failed} failed.")
    if failed > 0:
        sys.exit(1)
    print("STATUS: PASS — All RUM and session replay edge cases verified 100% green.")
    print("=================================================================")

if __name__ == "__main__":
    main()
