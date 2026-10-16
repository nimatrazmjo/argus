#!/usr/bin/env python3
"""
scripts/run_anomaly_e2e.py — End-to-end verification of Dynamic Anomaly & Forecast Monitors (Feature F019)
Tests:
1. Health and readiness of argus-anomaly-detector on port 9096.
2. Dynamic EWMA bounds calculation (mu +/- 3*sigma).
3. Seasonal diurnal decomposition: diurnal variation suppression vs off-peak anomaly firing.
4. Linear capacity saturation drift forecasting.
5. Injected anomaly detection, firing state transition, and automatic recovery.
6. 7-day diurnal replay benchmark reporting false positive rate (FPR < 1.0% vs static threshold).
7. Persists evidence under .harness/evidence/F019/.
"""

import sys
import os
import json
import time
import subprocess
import urllib.request
import urllib.error
from typing import Dict, Any, List

_default_evidence = "/tmp/evidence-f019"
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", _default_evidence)
PORT = 9096
BASE_URL = os.environ.get("ARGUS_ANOMALY_URL", f"http://127.0.0.1:{PORT}")

def ensure_port_forward():
    """Starts background kubectl port-forward if using localhost and port 9096 is not reachable."""
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
    # Wait for ready
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

def http_get(path: str) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def http_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    pf_proc = ensure_port_forward()
    transcript = []

    try:
        print("\n=================================================================")
        print("    FEATURE F019: ANOMALY & FORECAST MONITORS E2E VERIFICATION    ")
        print("=================================================================")

        # 1. Healthcheck
        print("\n[Step 1] Verifying Daemon Health & Active Monitors...")
        health = http_get("/healthz")
        assert health.get("status") == "ok", f"Healthcheck failed: {health}"
        print(f"[+] Healthcheck OK: {health}")
        transcript.append({"step": "healthcheck", "status": "ok", "response": health})

        # 2. Dynamic Monitor Algorithms Spec
        print("\n[Step 2] Documenting Dynamic Monitor Algorithm Specification...")
        monitors = http_get("/api/v1/monitors")
        algo_spec = {
            "feature": "F019",
            "name": "Dynamic Metric Anomaly Detection & Forecast Monitors",
            "algorithms": {
                "EWMA_Dynamic_Bands": {
                    "description": "Exponentially Weighted Moving Average with dynamic variance tracking and 3-sigma confidence bands",
                    "formulas": {
                        "moving_mean": "mu_t = alpha * x_t + (1 - alpha) * mu_{t-1}",
                        "moving_variance": "sigma_t^2 = beta * (x_t - mu_t)^2 + (1 - beta) * sigma_{t-1}^2",
                        "dynamic_upper_bound": "Upper_t = mu_t + k * sigma_t",
                        "dynamic_lower_bound": "Lower_t = max(0, mu_t - k * sigma_t)",
                        "z_score": "z_t = (x_t - mu_t) / sigma_t",
                        "firing_condition": "x_t > Upper_t or x_t < Lower_t"
                    },
                    "default_parameters": {
                        "alpha": 0.2,
                        "beta": 0.2,
                        "k_confidence": 3.0,
                        "min_warmup_points": 5,
                        "min_std_ratio": 0.05
                    }
                },
                "Seasonal_Diurnal_Decomposition": {
                    "description": "Additive seasonal decomposition modeling 24-hour diurnal cyclical periodicity",
                    "formulas": {
                        "decomposition": "Y(t) = Trend(t) + Seasonal(t mod 24) + Residual(t)",
                        "seasonal_update": "S_h = gamma * (Y_t - Trend_t) + (1 - gamma) * S_h",
                        "residual_evaluation": "|Residual_t| > k * sigma_R"
                    },
                    "parameters": {
                        "period_hours": 24,
                        "k_confidence": 3.0
                    }
                },
                "OLS_Saturation_Forecasting": {
                    "description": "Ordinary Least Squares rolling linear trend regression for Time-To-Exhaustion (TTE) prediction",
                    "formulas": {
                        "slope": "slope = sum((t_i - mean_t)*(y_i - mean_y)) / sum((t_i - mean_t)^2)",
                        "seconds_to_saturation": "T_exhaust = (Threshold - y_current) / slope"
                    }
                }
            },
            "active_monitors": monitors.get("monitors", {})
        }
        algo_file = os.path.join(EVIDENCE_DIR, "dynamic-monitor-algorithm.json")
        with open(algo_file, "w") as f:
            json.dump(algo_spec, f, indent=2)
        print(f"[+] Dynamic monitor algorithm specifications written to {algo_file}")

        # 3. Dynamic Baselining vs Normal Telemetry Evaluation
        print("\n[Step 3] Evaluating Normal Metric Ingestion & Dynamic Bounds...")
        metric_name = "e2e_service_latency"
        now = time.time()
        for i in range(10):
            val = 48.0 + (i % 3) * 1.5
            eval_res = http_post("/api/v1/evaluate", {
                "metric": metric_name,
                "value": val,
                "timestamp": now + (i * 60)
            })
            assert not eval_res["is_anomaly"], f"Normal value {val} falsely flagged as anomaly!"
            assert not eval_res["is_firing"], f"Normal value {val} falsely caused firing state!"

        print(f"[+] 10 normal observations evaluated cleanly: mean={eval_res['mean']}, bounds=[{eval_res['lower_bound']}, {eval_res['upper_bound']}]")
        transcript.append({"step": "normal_evaluation", "result": eval_res})

        # 4. Injected Metric Anomaly Detection & Firing State
        print("\n[Step 4] Injecting High-Magnitude Metric Anomaly & Verifying Firing...")
        anom_res = http_post("/api/v1/inject", {
            "metric": metric_name,
            "multiplier": 6.5
        })
        eval_anom = anom_res["evaluation"]
        assert eval_anom["is_anomaly"], f"Injected anomaly did NOT trigger is_anomaly! {eval_anom}"
        assert eval_anom["is_firing"], f"Injected anomaly did NOT set is_firing to True! {eval_anom}"
        assert eval_anom["z_score"] >= 3.0, f"Z-score {eval_anom['z_score']} did not exceed 3.0 sigma!"
        print(f"[+] Injected anomaly correctly detected: val={eval_anom['value']}, z-score={eval_anom['z_score']}, upper={eval_anom['upper_bound']}, firing={eval_anom['is_firing']}")
        transcript.append({"step": "anomaly_injection", "result": eval_anom})

        # 5. Anomaly Recovery
        print("\n[Step 5] Feeding Normal Telemetry & Verifying Automatic Monitor Recovery...")
        for i in range(5):
            rec_res = http_post("/api/v1/evaluate", {
                "metric": metric_name,
                "value": 49.0,
                "timestamp": now + 600 + (i * 60)
            })
        assert not rec_res["is_firing"], f"Monitor failed to recover after normal values resumed! {rec_res}"
        print(f"[+] Monitor successfully cleared and returned to normal: firing={rec_res['is_firing']}, bounds=[{rec_res['lower_bound']}, {rec_res['upper_bound']}]")
        transcript.append({"step": "recovery", "result": rec_res})

        # 6. Seasonal Diurnal Decomposition Test
        print("\n[Step 6] Testing Seasonal Diurnal Pattern Suppression...")
        seasonal_metric = "e2e_diurnal_traffic"
        # Train diurnal cycle across 2 full days (48 hours)
        start_t = 1776211200.0
        for day in range(2):
            for h in range(24):
                # Normal diurnal swing: 100 at night, 300 at midday
                diurnal_val = 200.0 + (100.0 * (1.0 if 9 <= h <= 17 else -0.8))
                http_post("/api/v1/evaluate/seasonal", {
                    "metric": seasonal_metric,
                    "value": diurnal_val,
                    "timestamp": start_t + ((day * 24 + h) * 3600)
                })

        # Midday peak test: 300 is normal for 14:00 on Day 3
        midday_res = http_post("/api/v1/evaluate/seasonal", {
            "metric": seasonal_metric,
            "value": 305.0,
            "timestamp": start_t + (2 * 24 * 3600) + (14 * 3600)
        })
        assert not midday_res["is_firing"], f"Normal diurnal midday peak falsely fired an anomaly! {midday_res}"
        print(f"[+] Midday diurnal peak (305 req/s) accepted as normal: is_firing={midday_res['is_firing']}")

        # Off-peak anomaly test: 350 at 03:00 AM on Day 3 is a major anomaly
        night_anom_res = http_post("/api/v1/evaluate/seasonal", {
            "metric": seasonal_metric,
            "value": 350.0,
            "timestamp": start_t + (2 * 24 * 3600) + (3 * 3600)
        })
        assert night_anom_res["is_firing"], f"Off-peak 3:00 AM traffic surge did NOT fire anomaly! {night_anom_res}"
        print(f"[+] Off-peak 3:00 AM surge (350 req/s) correctly detected as anomaly: z={night_anom_res['z_score']}, firing={night_anom_res['is_firing']}")
        transcript.append({"step": "seasonal_diurnal_test", "midday": midday_res, "night_anomaly": night_anom_res})

        # 7. Linear Drift Capacity Saturation Forecast
        print("\n[Step 7] Evaluating Capacity Saturation Drift Forecast...")
        # Memory growth: 60%, 65%, 70%, 75% over 15-minute intervals (900s)
        base_t = time.time()
        drift_points = [
            (base_t, 60.0),
            (base_t + 900, 65.0),
            (base_t + 1800, 70.0),
            (base_t + 2700, 75.0)
        ]
        forecast_res = http_post("/api/v1/forecast", {
            "points": drift_points,
            "target_threshold": 90.0
        })
        assert forecast_res["status"] == "ok", f"Forecast failed: {forecast_res}"
        assert forecast_res["slope_per_hour"] > 0, f"Slope should be positive: {forecast_res}"
        assert 0 < forecast_res["hours_to_saturation"] < 5.0, f"Unexpected saturation time: {forecast_res}"
        print(f"[+] Forecast verified: drift={forecast_res['slope_per_hour']}%/hr, hours_to_90%={forecast_res['hours_to_saturation']} hrs, R2={forecast_res['r_squared']}")
        transcript.append({"step": "forecast_drift", "result": forecast_res})

        # 8. Weekly Diurnal Replay Benchmark (False-Positive Evaluation)
        print("\n[Step 8] Running 7-Day Diurnal Benchmark Replay (10,080 data points)...")
        bench_res = http_post("/api/v1/benchmark", {"seed": 42})
        stat_eval = bench_res["static_threshold_evaluation"]
        dyn_eval = bench_res["dynamic_baselining_evaluation"]

        print(f"[+] Static Threshold (75ms): FPR={stat_eval['false_positive_rate_percent']}%, Precision={stat_eval['precision_percent']}%, F1={stat_eval['f1_score']}")
        print(f"[+] Dynamic Baselining:    FPR={dyn_eval['false_positive_rate_percent']}%, Precision={dyn_eval['precision_percent']}%, F1={dyn_eval['f1_score']}")

        assert dyn_eval["false_positive_rate_percent"] < 1.0, f"Dynamic FPR {dyn_eval['false_positive_rate_percent']}% exceeded 1.0% target!"
        assert dyn_eval["true_positive_rate_percent"] >= 90.0, f"Dynamic TPR {dyn_eval['true_positive_rate_percent']}% below 90% target!"
        assert stat_eval["false_positive_rate_percent"] > 10.0, f"Static FPR {stat_eval['false_positive_rate_percent']}% was expected to fail on diurnal peaks!"

        bench_file = os.path.join(EVIDENCE_DIR, "false-positive-benchmark.json")
        with open(bench_file, "w") as f:
            json.dump(bench_res, f, indent=2)
        print(f"[+] False-positive benchmark report saved to {bench_file}")

        # Save Anomaly Firing Transcript
        transcript_file = os.path.join(EVIDENCE_DIR, "anomaly-firing-transcript.json")
        with open(transcript_file, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "test_suite": "run_anomaly_e2e.py",
                "status": "PASS",
                "transcript": transcript
            }, f, indent=2)
        print(f"[+] Anomaly firing transcript saved to {transcript_file}")

        print("\n=================================================================")
        print("STATUS: PASS — All Feature F019 E2E checks passed successfully.")
        print("=================================================================")

    finally:
        if pf_proc:
            pf_proc.terminate()

if __name__ == "__main__":
    main()
