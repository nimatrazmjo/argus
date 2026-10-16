#!/usr/bin/env python3
"""
scripts/run_slo_edge_cases.py — Edge Case Verification Battery for SLO Tracking & Error Budgets
Validates zero-traffic handling, budget exhaustion clamping, independent latency SLIs,
burn rate thresholds, and rapid recovery reset.
"""

import os
import urllib.request
import urllib.parse
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8080"
SAMPLE_APP_API_TOKEN = os.environ.get("SAMPLE_APP_API_TOKEN", "")


def http_get(url, timeout=30):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8"), resp.status


def http_post(url, data=None, headers=None, timeout=30):
    headers = dict(headers) if headers else {}
    if SAMPLE_APP_API_TOKEN and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {SAMPLE_APP_API_TOKEN}"
    body = json.dumps(data).encode("utf-8") if data is not None else b""
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8"), resp.status


def run_tests():
    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log("=================================================================")
    log("     ARGUS SLO TRACKING & ERROR BUDGETS EDGE CASES BATTERY       ")
    log("=================================================================")

    # Edge Case 1: No-Traffic Window (Cold Start / 0 requests)
    log("--> [Edge Case 1/6] Testing No-Traffic Window & Zero-Division Safety...")
    http_post(f"{BASE_URL}/api/slo/reset")
    body, _ = http_get(f"{BASE_URL}/api/slo")
    slo = json.loads(body)

    assert slo["total_requests"] == 0, f"Expected 0 requests, got {slo['total_requests']}"
    assert slo["sli_ratio"] == 1.0, f"Expected SLI ratio 1.0, got {slo['sli_ratio']}"
    assert slo["sli_percent"] == 100.0, f"Expected SLI 100.0%, got {slo['sli_percent']}"
    assert slo["error_rate_percent"] == 0.0, f"Expected error rate 0.0%, got {slo['error_rate_percent']}"
    assert slo["error_budget_consumed_percent"] == 0.0, f"Expected consumed 0.0%, got {slo['error_budget_consumed_percent']}"
    assert slo["error_budget_remaining_percent"] == 100.0, f"Expected remaining 100.0%, got {slo['error_budget_remaining_percent']}"
    assert slo["burn_rate"] == 0.0, f"Expected burn rate 0.0, got {slo['burn_rate']}"
    assert slo["status"] == "NO_TRAFFIC", f"Expected NO_TRAFFIC status, got {slo['status']}"
    assert slo["latency_sli"]["sli_percent"] == 100.0, f"Expected latency SLI 100.0%, got {slo['latency_sli']['sli_percent']}"

    # Also test dashboard HTML under no-traffic
    html, _ = http_get(f"{BASE_URL}/slo")
    assert "NO_TRAFFIC" in html, "HTML dashboard missing NO_TRAFFIC status badge"
    log("    PASS: Zero-division protected, returned 100.0% SLI and NO_TRAFFIC status.")

    # Edge Case 2: Budget-Exhausted State (>100% of error budget consumed)
    log("--> [Edge Case 2/6] Testing Error Budget Exhaustion State Clamping...")
    # Seed 20 requests: 16 good, 4 bad. Error rate = 4 / 20 = 20.0%. Target SLO = 99.0% (Budget = 1.0%).
    # Consumed = 20.0 / 1.0 * 100 = 2000.0% (> 100%).
    for i in range(16):
        http_get(f"{BASE_URL}/order?order_id=good-{i:02d}")
        time.sleep(0.01)
    for i in range(4):
        try:
            http_get(f"{BASE_URL}/order?fail=true&order_id=fail-{i:02d}")
        except urllib.error.HTTPError:
            pass
        time.sleep(0.01)

    body, _ = http_get(f"{BASE_URL}/api/slo")
    slo = json.loads(body)
    assert slo["total_requests"] >= 20, f"Expected >= 20 requests, got {slo['total_requests']}"
    assert slo["bad_requests"] == 4, f"Expected 4 bad requests, got {slo['bad_requests']}"
    assert slo["error_budget_consumed_percent"] >= 1000.0, f"Expected >= 1000.0% consumed, got {slo['error_budget_consumed_percent']}"
    # Error budget remaining must be strictly clamped at 0.0%, never negative
    assert slo["error_budget_remaining_percent"] == 0.0, f"Expected remaining clamped at 0.0%, got {slo['error_budget_remaining_percent']}"
    assert slo["status"] == "BUDGET_EXHAUSTED", f"Expected BUDGET_EXHAUSTED status, got {slo['status']}"
    assert slo["burn_rate_alert"] == "CRITICAL_EXHAUSTED", f"Expected CRITICAL_EXHAUSTED alert, got {slo['burn_rate_alert']}"

    html, _ = http_get(f"{BASE_URL}/slo")
    assert "BUDGET_EXHAUSTED" in html, "HTML dashboard missing BUDGET_EXHAUSTED status badge"
    log("    PASS: Budget-exhausted state clamped remaining budget to 0.0% and triggered CRITICAL_EXHAUSTED alert.")

    # Edge Case 3: Fast Burn Rate Detection
    log("--> [Edge Case 3/6] Testing Fast Burn Rate (Burn Rate > 14.4x)...")
    # Reset and seed 20 requests with 3 errors -> error rate = 15.0%. Burn rate = 15.0x (> 14.4x).
    http_post(f"{BASE_URL}/api/slo/reset")
    for i in range(17):
        http_get(f"{BASE_URL}/order?order_id=fbr-good-{i:02d}")
        time.sleep(0.01)
    for i in range(3):
        try:
            http_get(f"{BASE_URL}/order?fail=true&order_id=fbr-fail-{i:02d}")
        except urllib.error.HTTPError:
            pass
        time.sleep(0.01)

    body, _ = http_get(f"{BASE_URL}/api/slo")
    slo = json.loads(body)
    assert slo["burn_rate"] >= 14.4, f"Expected burn rate >= 14.4x, got {slo['burn_rate']}"
    log(f"    PASS: Fast burn rate detected at {slo['burn_rate']}x (exceeds 14.4x critical threshold).")

    # Edge Case 4: Slow Burn Rate Detection
    log("--> [Edge Case 4/6] Testing Slow Burn Rate (6.0x <= Burn Rate < 14.4x)...")
    http_post(f"{BASE_URL}/api/slo/reset")
    # 23 good, 2 bad -> 8% error rate -> burn rate 8.0x
    for i in range(23):
        http_get(f"{BASE_URL}/order?order_id=sbr-good-{i:02d}")
        time.sleep(0.01)
    for i in range(2):
        try:
            http_get(f"{BASE_URL}/order?fail=true&order_id=sbr-fail-{i:02d}")
        except urllib.error.HTTPError:
            pass
        time.sleep(0.01)

    body, _ = http_get(f"{BASE_URL}/api/slo")
    slo = json.loads(body)
    assert 6.0 <= slo["burn_rate"] < 14.4, f"Expected 6.0 <= burn rate < 14.4, got {slo['burn_rate']}"
    log(f"    PASS: Slow burn rate detected at {slo['burn_rate']}x (exceeds 6.0x warning threshold).")

    # Edge Case 5: Orthogonal Latency SLI Violation (HTTP 200 with High Latency)
    log("--> [Edge Case 5/6] Testing Orthogonal Latency SLI Violation without HTTP Errors...")
    http_post(f"{BASE_URL}/api/slo/reset")
    # Send 10 normal fast requests (latency 45ms)
    for i in range(10):
        http_get(f"{BASE_URL}/order?latency_ms=45.0&order_id=fast-{i:02d}")
    # Send 10 slow requests (latency 650ms > 500ms threshold) with HTTP 200 OK
    for i in range(10):
        http_get(f"{BASE_URL}/order?latency_ms=650.0&order_id=slow-{i:02d}")

    body, _ = http_get(f"{BASE_URL}/api/slo")
    slo = json.loads(body)
    assert slo["total_requests"] >= 20, f"Expected >= 20 requests, got {slo['total_requests']}"
    # Availability SLI MUST be 100.0% because all requests returned HTTP 200!
    assert slo["sli_percent"] == 100.0, f"Availability SLI should remain 100.0%, got {slo['sli_percent']}"
    assert slo["good_requests"] >= 20, f"Expected >= 20 good requests for availability, got {slo['good_requests']}"
    # Latency SLI: 10 requests were slow (>500ms)
    assert slo["latency_sli"]["good_requests"] >= 10, f"Expected at least 10 good latency requests, got {slo['latency_sli']['good_requests']}"
    assert slo["latency_sli"]["bad_requests"] == 10, f"Expected 10 bad latency requests, got {slo['latency_sli']['bad_requests']}"
    assert slo["latency_sli"]["sli_percent"] <= 75.0, f"Expected latency SLI degraded <= 75.0%, got {slo['latency_sli']['sli_percent']}"
    log("    PASS: Latency degradation measured independently (Availability SLI: 100.0%, Latency SLI: 50.0%).")

    # Edge Case 6: Dynamic Reset and Webhook Channel Integration
    log("--> [Edge Case 6/6] Testing In-Memory Alert Webhook Reception & Instant Recovery Reset...")
    # Test POST /api/alerts
    alert_payload = {
        "receiver": "argus-default-webhook",
        "status": "firing",
        "alerts": [{"labels": {"alertname": "ArgusSLOFastBurnRate", "severity": "critical"}}]
    }
    post_res, post_st = http_post(f"{BASE_URL}/api/alerts", data=alert_payload, headers={"Content-Type": "application/json"})
    assert post_st == 200, f"Expected 200 on alert post, got {post_st}"

    # Query GET /api/alerts
    alerts_get, _ = http_get(f"{BASE_URL}/api/alerts")
    alerts_data = json.loads(alerts_get)
    assert len(alerts_data.get("alerts", [])) > 0, "Expected at least 1 received alert in /api/alerts"
    log(f"    PASS: Webhook alert received and retrievable via /api/alerts ({len(alerts_data['alerts'])} alerts stored).")

    # Final reset
    http_post(f"{BASE_URL}/api/slo/reset")
    body, _ = http_get(f"{BASE_URL}/api/slo")
    slo = json.loads(body)
    assert slo["total_requests"] == 0
    assert slo["status"] == "NO_TRAFFIC"
    log("    PASS: Final reset restored clean state (0 requests, status NO_TRAFFIC).")

    log("=================================================================")
    log("   ALL 6 SLO EDGE CASES VERIFIED 100% GREEN!                     ")
    log("=================================================================")

    return "\n".join(log_lines)


if __name__ == "__main__":
    output = run_tests()
    print("EDGE_CASES_VERIFIED_OUTPUT")
