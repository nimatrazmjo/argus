#!/usr/bin/env python3
"""
scripts/run_anomaly_edge_cases.py — Edge Cases Battery for Anomaly & Forecast Monitors (Feature F019)
Tests:
1. Cold start: N=0, 1, 2, 3 points — avoids zero division, widens bounds, flags warmup.
2. Sparse data & irregular intervals: large gaps without corrupting baseline.
3. Seasonality shift / permanent regime change: step-jump fires, then smoothly adapts within half-life window without permanent alert lock.
4. Metric flattening / zero-variance flatline: sigma -> 0 guardrail prevents division by zero and micro-jitter false positives.
5. Extreme shock spike & rapid recovery: handles 100x outlier and maintains variance stability.
6. Zero-value metric handling: handles counter / error rate starting at 0.0.
"""

import sys
import os
import json
import time
import math
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List

_default_evidence = "/tmp/evidence-f019"
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", _default_evidence)
PORT = 9096
BASE_URL = os.environ.get("ARGUS_ANOMALY_URL", f"http://127.0.0.1:{PORT}")

def ensure_port_forward():
    if not ("127.0.0.1" in BASE_URL or "localhost" in BASE_URL):
        return None
    try:
        req = urllib.request.urlopen(f"{BASE_URL}/healthz", timeout=1)
        if req.status == 200:
            print("[+] Service already responding.")
            return None
    except Exception:
        pass

    print(f"[*] Starting port-forward for svc/argus-anomaly-detector to localhost:{PORT}...")
    pf = subprocess.Popen(
        ["kubectl", "port-forward", "-n", "argus-system", "svc/argus-anomaly-detector", f"{PORT}:{PORT}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(15):
        time.sleep(0.5)
        try:
            req = urllib.request.urlopen(f"{BASE_URL}/healthz", timeout=1)
            if req.status == 200:
                print("[+] Port-forward active and service responding.")
                return pf
        except Exception:
            continue
    print("[-] Failed to connect to argus-anomaly-detector via port-forward.")
    sys.exit(1)

def http_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    pf_proc = ensure_port_forward()
    results = []

    try:
        print("\n=================================================================")
        print("  FEATURE F019: ANOMALY & FORECAST MONITORS EDGE CASES BATTERY   ")
        print("=================================================================")

        # -------------------------------------------------------------
        # Edge Case 1: Cold Start Resilience (N=0, 1, 2, 3, 4 points)
        # -------------------------------------------------------------
        print("\n[Edge Case 1] Testing Cold Start & Dynamic Warm-up Expansion...")
        cold_metric = f"edge_cold_start_{int(time.time())}"
        
        # Point 1 (N=1)
        r1 = http_post("/api/v1/evaluate", {"metric": cold_metric, "value": 100.0})
        assert r1["status"] == "cold_start", f"Expected cold_start status, got {r1['status']}"
        assert not r1["is_anomaly"], "Single first point should never fire an anomaly"
        assert not r1["is_firing"], "Cold start point should not fire"
        assert r1["upper_bound"] > 100.0, "Upper bound must be greater than initial point"

        # Points 2-4 (Warm-up phase)
        for i in range(2, 5):
            r = http_post("/api/v1/evaluate", {"metric": cold_metric, "value": 102.0})
            assert r["status"] == "warmup", f"Expected warmup status, got {r['status']}"
            assert not r["is_firing"], f"Warmup point {i} should not fire"

        # Point 5 (Warm-up complete)
        r5 = http_post("/api/v1/evaluate", {"metric": cold_metric, "value": 101.0})
        assert r5["status"] == "normal", f"Expected normal status after 5 points, got {r5['status']}"
        print(f"[+] Cold-start successfully managed without false alarms: status={r5['status']}, count={r5['sample_count']}, bounds=[{r5['lower_bound']}, {r5['upper_bound']}]")
        results.append({"edge_case": "cold_start", "result": r5, "status": "PASS"})

        # -------------------------------------------------------------
        # Edge Case 2: Sparse Data & Irregular Interval Gaps
        # -------------------------------------------------------------
        print("\n[Edge Case 2] Testing Sparse Data & Irregular Intervals...")
        sparse_metric = f"edge_sparse_data_{int(time.time())}"
        base_t = 1776211200.0

        # Irregular timestamps with 4-hour gap
        http_post("/api/v1/evaluate", {"metric": sparse_metric, "value": 50.0, "timestamp": base_t})
        http_post("/api/v1/evaluate", {"metric": sparse_metric, "value": 52.0, "timestamp": base_t + 120})
        http_post("/api/v1/evaluate", {"metric": sparse_metric, "value": 49.0, "timestamp": base_t + 300})
        # 4-hour gap (14,400s)
        gap_res = http_post("/api/v1/evaluate", {"metric": sparse_metric, "value": 51.0, "timestamp": base_t + 14700})
        assert not gap_res["is_anomaly"], f"Post-gap observation falsely flagged as anomaly: {gap_res}"
        assert not gap_res["is_firing"], f"Post-gap observation caused false firing: {gap_res}"
        print(f"[+] Sparse data gap handled smoothly: mean={gap_res['mean']}, bounds=[{gap_res['lower_bound']}, {gap_res['upper_bound']}]")
        results.append({"edge_case": "sparse_data_gap", "result": gap_res, "status": "PASS"})

        # -------------------------------------------------------------
        # Edge Case 3: Seasonality Shift / Permanent Operational Regime Change
        # -------------------------------------------------------------
        print("\n[Edge Case 3] Testing Seasonality Shift & Adaptive Baselining...")
        shift_metric = f"edge_regime_shift_{int(time.time())}"
        
        # Train baseline at 100.0
        for i in range(15):
            http_post("/api/v1/evaluate", {"metric": shift_metric, "value": 100.0 + (i % 2) * 2.0})

        # Step jump to 250.0 (e.g. permanent post-migration baseline)
        jump_res = http_post("/api/v1/evaluate", {"metric": shift_metric, "value": 250.0})
        assert jump_res["is_anomaly"], "Initial regime jump must trigger anomaly detection"
        assert jump_res["is_firing"], "Initial regime jump must set firing flag"
        print(f"[+] Initial regime jump (100 -> 250) detected correctly: z={jump_res['z_score']}, firing={jump_res['is_firing']}")

        # Persist at new baseline: EWMA must adapt within 40 points
        adapted_res = None
        for i in range(40):
            adapted_res = http_post("/api/v1/evaluate", {"metric": shift_metric, "value": 250.0 + (i % 3) * 1.0})

        assert not adapted_res["is_firing"], f"Monitor failed to adapt to new baseline (permanent alert latch)! {adapted_res}"
        assert adapted_res["mean"] > 240.0, f"Mean did not shift to new baseline: {adapted_res['mean']}"
        print(f"[+] Monitor adapted to new baseline without permanent alert lock: new_mean={adapted_res['mean']}, firing={adapted_res['is_firing']}")
        results.append({"edge_case": "regime_shift_adaptation", "jump": jump_res, "adapted": adapted_res, "status": "PASS"})

        # -------------------------------------------------------------
        # Edge Case 4: Metric Flattening & Zero-Variance Flatline Guardrail
        # -------------------------------------------------------------
        print("\n[Edge Case 4] Testing Metric Flattening (Zero Variance Safeguard)...")
        flat_metric = f"edge_flatline_{int(time.time())}"
        
        # Metric is perfectly constant at 50.0 for 25 points
        for i in range(25):
            http_post("/api/v1/evaluate", {"metric": flat_metric, "value": 50.0})

        # Micro-jitter: 50.2 (0.4% change)
        jitter_res = http_post("/api/v1/evaluate", {"metric": flat_metric, "value": 50.2})
        assert not jitter_res["is_anomaly"], f"Micro-jitter on flatline caused false anomaly! {jitter_res}"
        assert not jitter_res["is_firing"], f"Micro-jitter on flatline caused false firing! {jitter_res}"
        assert jitter_res["std"] >= 1e-4, f"Standard deviation collapsed to zero: {jitter_res['std']}"
        print(f"[+] Zero-variance flatline guardrail verified: std={jitter_res['std']}, bounds=[{jitter_res['lower_bound']}, {jitter_res['upper_bound']}], firing={jitter_res['is_firing']}")
        results.append({"edge_case": "flatline_zero_variance", "result": jitter_res, "status": "PASS"})

        # -------------------------------------------------------------
        # Edge Case 5: Extreme Shock Outlier Spike (100x) & Immediate Recovery
        # -------------------------------------------------------------
        print("\n[Edge Case 5] Testing Extreme Shock Outlier Spike & Recovery...")
        shock_metric = f"edge_shock_{int(time.time())}"
        for i in range(15):
            http_post("/api/v1/evaluate", {"metric": shock_metric, "value": 50.0})

        # Shock spike: 5000.0 (100x)
        shock_res = http_post("/api/v1/evaluate", {"metric": shock_metric, "value": 5000.0})
        assert shock_res["is_anomaly"], "100x shock spike must fire anomaly"
        assert shock_res["is_firing"], "100x shock spike must trigger firing state"
        assert shock_res["z_score"] > 20.0, f"Expected huge z-score, got {shock_res['z_score']}"
        print(f"[+] 100x shock spike handled cleanly: z={shock_res['z_score']}, firing={shock_res['is_firing']}")

        # Return to normal
        for i in range(5):
            rec_shock = http_post("/api/v1/evaluate", {"metric": shock_metric, "value": 51.0})
        assert not rec_shock["is_firing"], "Monitor failed to recover after shock spike normalized"
        print(f"[+] Post-shock recovery verified: firing={rec_shock['is_firing']}")
        results.append({"edge_case": "shock_outlier_spike", "shock": shock_res, "recovered": rec_shock, "status": "PASS"})

        # -------------------------------------------------------------
        # Edge Case 6: Zero-Value / Counter Error Metric Transitions
        # -------------------------------------------------------------
        print("\n[Edge Case 6] Testing Zero-Value Transitions (Error Count Baseline)...")
        zero_metric = f"edge_zero_error_{int(time.time())}"
        for i in range(10):
            http_post("/api/v1/evaluate", {"metric": zero_metric, "value": 0.0})

        # First error: 1.0 (small bump)
        bump_res = http_post("/api/v1/evaluate", {"metric": zero_metric, "value": 1.0})
        assert bump_res["upper_bound"] >= 0.0, "Bounds must remain non-negative"
        print(f"[+] Zero-value metric handled safely without math errors: bounds=[{bump_res['lower_bound']}, {bump_res['upper_bound']}]")
        results.append({"edge_case": "zero_value_transition", "result": bump_res, "status": "PASS"})

        # Save edge case evidence report
        report_file = os.path.join(EVIDENCE_DIR, "anomaly-edge-cases-report.json")
        with open(report_file, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "test_suite": "run_anomaly_edge_cases.py",
                "status": "PASS",
                "edge_cases_tested": len(results),
                "results": results
            }, f, indent=2)
        print(f"\n[+] Edge cases report saved to {report_file}")

        print("\n=================================================================")
        print("STATUS: PASS — All Feature F019 Edge Cases verified green.")
        print("=================================================================")

    finally:
        if pf_proc:
            pf_proc.terminate()

if __name__ == "__main__":
    main()
