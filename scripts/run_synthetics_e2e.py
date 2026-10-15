#!/usr/bin/env python3
"""
Argus Feature F018 Synthetic Canary Probing Verification Controller
Validates synthetic transaction execution, multi-step latency metrics,
simulated target failure detection, and automatic recovery.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error

PROBER_URL = os.environ.get("PROBER_URL", "http://argus-synthetic-prober.argus-system.svc.cluster.local:9115")
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", "/tmp/evidence-f018")

def http_get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

def http_post(url: str, data: dict = None) -> tuple[int, str]:
    body = json.dumps(data).encode("utf-8") if data else b""
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")

def main():
    print("=================================================================")
    print("       ARGUS SYNTHETIC CANARY PROBING PROOF (F018)               ")
    print("=================================================================")

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # 1. Reset state
    print("--> [1/5] Ensuring prober is in clean baseline state...")
    http_post(f"{PROBER_URL}/api/simulate/recover_target")

    # 2. Run ad-hoc probe
    print("--> [2/5] Triggering multi-step synthetic transaction workflow...")
    status, body = http_post(f"{PROBER_URL}/api/run")
    if status != 200:
        print(f"ERROR: Prober failed to execute: {body}", file=sys.stderr)
        sys.exit(1)

    probe_data = json.loads(body)
    print(f"    Synthetic run completed: success={probe_data.get('success')}, duration={probe_data.get('duration_seconds'):.4f}s")
    for s in probe_data.get("steps", []):
        print(f"      - Step [{s.get('name')}]: code={s.get('status_code')}, duration={s.get('duration_seconds'):.4f}s, success={s.get('success')}")

    if probe_data.get("success") != 1:
        print(f"ERROR: Expected synthetic probe success == 1, got {probe_data}", file=sys.stderr)
        sys.exit(1)

    with open(f"{EVIDENCE_DIR}/synthetic-probe-success.json", "w") as f:
        json.dump(probe_data, f, indent=2)

    # 3. Inspect Prometheus Metrics
    print("--> [3/5] Querying Prometheus metrics exposition from prober (:9115/metrics)...")
    status, metrics_text = http_get(f"{PROBER_URL}/metrics")
    if status != 200 or "argus_synthetic_probe_success" not in metrics_text:
        print(f"ERROR: Failed to fetch Prometheus metrics: {metrics_text}", file=sys.stderr)
        sys.exit(1)

    print("    Prometheus metrics verified:")
    for line in metrics_text.splitlines():
        if "argus_synthetic_probe" in line and not line.startswith("#"):
            print(f"      {line}")

    with open(f"{EVIDENCE_DIR}/synthetic-metrics-raw.txt", "w") as f:
        f.write(metrics_text)

    # 4. Simulate Target Failure
    print("--> [4/5] Simulating target outage and asserting probe failure detection...")
    status, _ = http_post(f"{PROBER_URL}/api/simulate/fail_target")
    status, fail_metrics = http_get(f"{PROBER_URL}/metrics")

    found_zero = False
    for line in fail_metrics.splitlines():
        if "argus_synthetic_probe_success" in line and not line.startswith("#"):
            val = line.split()[-1]
            if val == "0":
                found_zero = True
                print(f"    PASS: Outage detected! Metric reading: {line}")
                break

    if not found_zero:
        print(f"ERROR: Expected argus_synthetic_probe_success == 0 during outage!", file=sys.stderr)
        sys.exit(1)

    with open(f"{EVIDENCE_DIR}/synthetic-probe-failure.json", "w") as f:
        json.dump({"outage_metric_detected": "0", "status": "FAIL_DETECTED"}, f, indent=2)

    # 5. Restore Target
    print("--> [5/5] Restoring target service and confirming automatic probe recovery...")
    http_post(f"{PROBER_URL}/api/simulate/recover_target")
    status, recovered_metrics = http_get(f"{PROBER_URL}/metrics")

    found_recovery = False
    for line in recovered_metrics.splitlines():
        if "argus_synthetic_probe_success" in line and not line.startswith("#"):
            val = line.split()[-1]
            if val == "1":
                found_recovery = True
                print(f"    PASS: Target recovery confirmed! Metric reading: {line}")
                break

    if not found_recovery:
        print(f"ERROR: Expected argus_synthetic_probe_success == 1 after recovery!", file=sys.stderr)
        sys.exit(1)

    print("=================================================================")
    print("   FEATURE F018 SYNTHETIC PROBING VERIFIED 100% GREEN!           ")
    print("=================================================================")

if __name__ == "__main__":
    main()
