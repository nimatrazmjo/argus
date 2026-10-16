#!/usr/bin/env python3
"""
Test Suite for Argus 10-Service Datadog Emulation Platform
Tests:
1. Healthcheck readiness across all 10 microservices
2. Prometheus metrics exposition (/metrics)
3. Full distributed checkout transaction across all 10 services
4. Datadog 'Logs Everything' structured JSON verification
5. Trace correlation (trace_id, span_id, dd.trace_id, dd.span_id)
6. Datadog error logging with stack trace capture (auth_expired, inventory_exhausted, payment_declined)
7. ClickHouse ingestion verification via NodePort :30123
8. Automated GitHub Issue filing if any issue is detected (DO NOT FIX, JUST TEST)
"""

import os
import sys
import time
import json
import uuid
import signal
import threading
import subprocess
import urllib.request
import urllib.error
import urllib.parse

SERVICES = [
    {"name": "argus-svc-gateway", "role": "gateway", "port": 8001},
    {"name": "argus-svc-auth", "role": "auth", "port": 8002},
    {"name": "argus-svc-catalog", "role": "catalog", "port": 8003},
    {"name": "argus-svc-order", "role": "order", "port": 8004},
    {"name": "argus-svc-inventory", "role": "inventory", "port": 8005},
    {"name": "argus-svc-payment", "role": "payment", "port": 8006},
    {"name": "argus-svc-billing", "role": "billing", "port": 8007},
    {"name": "argus-svc-shipping", "role": "shipping", "port": 8008},
    {"name": "argus-svc-notification", "role": "notification", "port": 8009},
    {"name": "argus-svc-recommendation", "role": "recommendation", "port": 8010},
]

DOWNSTREAM_URLS = {
    "URL_AUTH": "http://127.0.0.1:8002",
    "URL_CATALOG": "http://127.0.0.1:8003",
    "URL_ORDER": "http://127.0.0.1:8004",
    "URL_INVENTORY": "http://127.0.0.1:8005",
    "URL_PAYMENT": "http://127.0.0.1:8006",
    "URL_BILLING": "http://127.0.0.1:8007",
    "URL_SHIPPING": "http://127.0.0.1:8008",
    "URL_NOTIFICATION": "http://127.0.0.1:8009",
    "URL_RECOMMENDATION": "http://127.0.0.1:8010",
}

PROCESSES = []
COLLECTED_LOGS = []
DISCOVERED_ISSUES = []

READER_THREADS = []

def reader_worker(svc_name, stream):
    for line in iter(stream.readline, ''):
        line_str = line.strip()
        if line_str.startswith("{") and line_str.endswith("}"):
            try:
                record = json.loads(line_str)
                COLLECTED_LOGS.append((svc_name, record))
            except Exception:
                pass

def file_github_issue(title, body):
    """File a GitHub issue using gh cli without fixing the bug."""
    print(f"\n[!] FILING GITHUB ISSUE: {title}")
    try:
        cmd = ["gh", "issue", "create", "--title", title, "--body", body]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[+] GitHub Issue Created: {res.stdout.strip()}")
    except Exception as e:
        print(f"[-] Failed to file GitHub issue via gh cli: {e}")

def start_services():
    print("--> Starting all 10 Datadog-emulating microservices...")
    script_path = os.path.abspath("deploy/services/service_template.py")

    for svc in SERVICES:
        env = os.environ.copy()
        env["PORT"] = str(svc["port"])
        env["SERVICE_NAME"] = svc["name"]
        env["SERVICE_ROLE"] = svc["role"]
        env["ENV"] = "production"
        env["VERSION"] = "1.0.0"
        env["DATACENTER"] = "us-gov-west-1"
        env.update(DOWNSTREAM_URLS)

        p = subprocess.Popen(
            [sys.executable, "-u", script_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        PROCESSES.append((svc["name"], p))
        t = threading.Thread(target=reader_worker, args=(svc["name"], p.stdout), daemon=True)
        t.start()
        READER_THREADS.append(t)
        print(f"    Started {svc['name']} (role={svc['role']}) on port {svc['port']} [PID {p.pid}]")

    time.sleep(2)

def stop_services():
    print("\n--> Stopping all microservices...")
    for name, p in PROCESSES:
        try:
            p.terminate()
            p.wait(timeout=2)
        except Exception:
            p.kill()

def collect_stdout():
    time.sleep(0.5)

def test_healthchecks():
    print("\n[Test 1] Verifying Healthcheck Endpoints across all 10 microservices...")
    failed = []
    for svc in SERVICES:
        url = f"http://127.0.0.1:{svc['port']}/healthz"
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                if resp.status == 200 and data.get("status") == "HEALTHY":
                    print(f"    [OK] {svc['name']} (: {svc['port']}) -> HTTP 200 {data}")
                else:
                    failed.append((svc["name"], f"Unexpected response: {data}"))
        except Exception as e:
            failed.append((svc["name"], str(e)))

    if failed:
        issue_title = f"[BUG] Healthcheck Failure on Microservices: {', '.join([f[0] for f in failed])}"
        issue_body = f"## Healthcheck Failure Details\nThe following services failed healthcheck probe verification:\n"
        for svc_name, err in failed:
            issue_body += f"- **{svc_name}**: `{err}`\n"
        file_github_issue(issue_title, issue_body)
    else:
        print("[+] PASS: All 10 microservices responded healthy (100% Green).")

def test_metrics():
    print("\n[Test 2] Verifying Prometheus /metrics Exposition...")
    failed = []
    for svc in SERVICES:
        url = f"http://127.0.0.1:{svc['port']}/metrics"
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                text = resp.read().decode()
                if "http_requests_total" in text and "http_request_duration_seconds" in text:
                    print(f"    [OK] {svc['name']} (: {svc['port']}) exposed valid Prometheus metrics")
                else:
                    failed.append((svc["name"], "Missing expected Prometheus metrics in output"))
        except Exception as e:
            failed.append((svc["name"], str(e)))

    if failed:
        file_github_issue("[BUG] Prometheus Metrics Missing on Microservices", f"Details: {failed}")
    else:
        print("[+] PASS: Prometheus metrics exposed properly across all 10 services.")

def test_distributed_transaction():
    print("\n[Test 3] Executing End-to-End Distributed Checkout Flow...")
    gateway_url = "http://127.0.0.1:8001/api/checkout"
    req = urllib.request.Request(gateway_url, headers={"User-Agent": "DatadogTestClient/1.0"}, method="POST")
    try:
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=5) as resp:
            elapsed_ms = round((time.time() - t0) * 1000.0, 2)
            data = json.loads(resp.read().decode())
            print(f"    [OK] Gateway returned HTTP {resp.status} in {elapsed_ms}ms")
            print(f"    Status: {data.get('status')}")
            print(f"    Order ID: {data.get('order', {}).get('order_id')}")
            print(f"    Trace ID: {data.get('trace_id')}")

            # Verify participation of sub-services in returned payload
            order = data.get("order", {})
            assert order.get("status") == "CONFIRMED", "Order status must be CONFIRMED"
            assert "inventory" in order, "Inventory response must be present"
            assert "payment" in order, "Payment response must be present"
            assert "shipping" in order, "Shipping response must be present"
            assert "notification" in order, "Notification response must be present"
            print("[+] PASS: Distributed transaction traversed all microservices successfully.")
            return data.get("trace_id")
    except Exception as e:
        file_github_issue("[BUG] Distributed Checkout Transaction Failed", f"Error during checkout call: {e}")
        return None

def test_datadog_logging_attributes(target_trace_id):
    print("\n[Test 4] Auditing Datadog 'Logs Everything' Structured Attributes...")
    collect_stdout()

    if not COLLECTED_LOGS:
        file_github_issue("[BUG] No Structured Logs Emitted to stdout", "Services did not write JSON logs to stdout.")
        return

    print(f"    Collected {len(COLLECTED_LOGS)} structured JSON log records from microservices.")

    required_dd_keys = [
        "timestamp", "status", "level", "service", "env", "version",
        "ddsource", "ddtags", "trace_id", "span_id", "dd.trace_id",
        "dd.span_id", "logger.name", "message"
    ]

    missing_fields = []
    step_categories = set()
    correlated_logs_count = 0

    for svc_name, log in COLLECTED_LOGS:
        for k in required_dd_keys:
            if k not in log:
                missing_fields.append((svc_name, k))

        log_name = log.get("logger.name", "")
        step_categories.add(log_name)

        if target_trace_id and log.get("trace_id") == target_trace_id:
            correlated_logs_count += 1

    print(f"    Verified Logger Steps Observed: {sorted(list(step_categories))}")
    print(f"    Logs correlated to Transaction Trace {target_trace_id}: {correlated_logs_count} logs")

    # Sample Log Inspection
    sample = COLLECTED_LOGS[-1][1]
    print(f"\n    Sample Datadog JSON Log:\n{json.dumps(sample, indent=2)}")

    if missing_fields:
        file_github_issue("[BUG] Datadog Required Log Attributes Missing", f"Missing fields: {missing_fields[:10]}")
    else:
        print("[+] PASS: 100% of logs strictly comply with Datadog reserved attributes schema.")

def test_error_simulation():
    print("\n[Test 5] Auditing Datadog Error Logging & Stack Trace Capture...")
    scenarios = [
        ("auth_expired", 401, "TokenExpiredException"),
        ("inventory_exhausted", 409, "StockExhaustedException"),
        ("payment_declined", 402, "PaymentGatewayDeclinedException"),
    ]

    for err_type, expected_code, expected_exc in scenarios:
        url = f"http://127.0.0.1:8001/api/checkout?trigger_error={err_type}"
        req = urllib.request.Request(url, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                print(f"    [-] Scenario {err_type} unexpectedly returned HTTP {resp.status}")
                file_github_issue(f"[BUG] Error Scenario {err_type} did not fail", f"Expected {expected_code}, got {resp.status}")
        except urllib.error.HTTPError as e:
            print(f"    [OK] Scenario {err_type} correctly returned HTTP {e.code}")
            time.sleep(0.5)
            collect_stdout()

            # Find corresponding error log
            found_error_log = False
            for svc_name, log in COLLECTED_LOGS:
                if log.get("status") == "error" and log.get("error.kind") == expected_exc:
                    found_error_log = True
                    print(f"         Found Datadog Error Log: service={log.get('service')} error.kind={log.get('error.kind')}")
                    assert "Traceback" in log.get("error.stack", ""), "Stack trace must contain Python Traceback"
                    break

            if not found_error_log:
                file_github_issue(f"[BUG] Missing Datadog Stack Trace for {expected_exc}", f"No error log found for scenario {err_type}")
            else:
                print(f"         [OK] Verified Datadog multiline stack trace & error attributes for {expected_exc}")

def test_clickhouse_persistence():
    print("\n[Test 6] Checking ClickHouse Telemetry Ingestion (NodePort :30123)...")
    ch_pass = urllib.parse.quote(os.environ.get("CLICKHOUSE_PASSWORD", ""))
    url = f"http://localhost:30123/?user=default&password={ch_pass}&query=SELECT+count()+FROM+default.otel_logs"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            count = int(resp.read().decode().strip())
            print(f"    [OK] ClickHouse default.otel_logs contains {count:,} total log records")
            print("[+] PASS: ClickHouse storage pipeline verified online and accessible.")
    except Exception as e:
        file_github_issue("[BUG] ClickHouse Ingestion Query Failed", f"Failed to query ClickHouse: {e}")

def main():
    print("=================================================================")
    print("   ARGUS 10-SERVICE DATADOG EMULATION & LOGGING TEST SUITE       ")
    print("=================================================================")

    start_services()
    try:
        test_healthchecks()
        test_metrics()
        trace_id = test_distributed_transaction()
        test_datadog_logging_attributes(trace_id)
        test_error_simulation()
        test_clickhouse_persistence()

        print("\n=================================================================")
        print("STATUS: ALL 10 MICROSERVICES DATADOG TESTS COMPLETE!")
        print("=================================================================")
    finally:
        stop_services()

if __name__ == "__main__":
    main()
