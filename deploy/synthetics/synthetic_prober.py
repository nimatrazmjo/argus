#!/usr/bin/env python3
"""
Argus Synthetic Canary Prober & Prometheus Exporter
Executes blackbox API checks, multi-step transaction flows, and authenticated endpoint probes.
Exposes standard Prometheus metrics on port 9115 (/metrics) for OTel Collector scraping.
"""

import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading

PORT = int(os.environ.get("PORT", "9115"))
SAMPLE_SERVICE_URL = os.environ.get("SAMPLE_SERVICE_URL", "http://argus-sample-service.argus-system.svc.cluster.local:8080").rstrip("/")
PROBE_INTERVAL = int(os.environ.get("PROBE_INTERVAL", "300"))
SYNTHETIC_BEARER_TOKEN = os.environ.get("SYNTHETIC_BEARER_TOKEN", "")


def verify_prober_auth(headers) -> tuple[bool, int, str]:
    """Authenticates state-changing requests via Authorization: Bearer or X-Synthetic-Token header."""
    if not SYNTHETIC_BEARER_TOKEN:
        return False, 500, "Server configuration error: SYNTHETIC_BEARER_TOKEN is not configured"
    header_tok = headers.get("X-Synthetic-Token", "").strip()
    if header_tok and hmac.compare_digest(header_tok, SYNTHETIC_BEARER_TOKEN):
        return True, 200, "OK"
    auth_header = headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        bearer_tok = auth_header.split(" ", 1)[1].strip()
        if bearer_tok and hmac.compare_digest(bearer_tok, SYNTHETIC_BEARER_TOKEN):
            return True, 200, "OK"
    return False, 401, "Unauthorized: valid Bearer or X-Synthetic-Token required"

# Global probe metrics & status
LOCK = threading.Lock()
PROBE_RESULTS = {}
PROBE_COUNTS = {"success": 0, "failure": 0}
SIMULATED_TARGET_FAILURE = False

def execute_http_probe(name: str, url: str, expected_code: int = 200, headers: dict = None, expected_substr: str = None) -> dict:
    """Executes a single HTTP probe step and records execution time."""
    start = time.time()
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            duration = time.time() - start
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
            success = (status == expected_code)
            if success and expected_substr and expected_substr not in body:
                success = False
            return {
                "name": name,
                "url": url,
                "status_code": status,
                "success": 1 if success else 0,
                "duration_seconds": duration,
                "error": None
            }
    except urllib.error.HTTPError as e:
        duration = time.time() - start
        return {
            "name": name,
            "url": url,
            "status_code": e.code,
            "success": 1 if e.code == expected_code else 0,
            "duration_seconds": duration,
            "error": f"HTTP {e.code}"
        }
    except Exception as e:
        duration = time.time() - start
        return {
            "name": name,
            "url": url,
            "status_code": 0,
            "success": 0,
            "duration_seconds": duration,
            "error": str(e)
        }

def run_all_probes() -> dict:
    """Executes the full suite of synthetic canary probes."""
    global PROBE_RESULTS, PROBE_COUNTS, SIMULATED_TARGET_FAILURE
    t_start = time.time()

    with LOCK:
        is_failing = SIMULATED_TARGET_FAILURE

    if is_failing:
        # Simulate complete target outage
        overall_success = 0
        overall_duration = 2.05
        steps = [
            {"name": "order_api", "success": 0, "duration_seconds": 2.05, "status_code": 503, "error": "SimulatedTargetFailure"}
        ]
    else:
        # Step 1: Sample Service API transaction probe
        step1 = execute_http_probe(
            name="order_api",
            url=f"{SAMPLE_SERVICE_URL}/order?order_id=synthetic-probe-{int(time.time())}",
            expected_code=200,
            expected_substr="success"
        )

        # Step 2: Sample Service SLO visual dashboard probe
        step2 = execute_http_probe(
            name="slo_dashboard",
            url=f"{SAMPLE_SERVICE_URL}/slo",
            expected_code=200,
            expected_substr="Argus // SLO & Error Budget Tracker"
        )

        # Step 3: Authenticated canary check (headers + token)
        step3 = execute_http_probe(
            name="auth_validation",
            url=f"{SAMPLE_SERVICE_URL}/healthz",
            expected_code=200,
            headers={"Authorization": f"Bearer {SYNTHETIC_BEARER_TOKEN}"} if SYNTHETIC_BEARER_TOKEN else {},
            expected_substr="healthy"
        )

        steps = [step1, step2, step3]
        overall_success = 1 if all(s["success"] == 1 for s in steps) else 0
        overall_duration = sum(s["duration_seconds"] for s in steps)

    with LOCK:
        PROBE_RESULTS = {
            "target": "argus-sample-service",
            "probe_type": "canary_workflow",
            "success": overall_success,
            "duration_seconds": overall_duration,
            "steps": steps,
            "timestamp": time.time()
        }
        if overall_success == 1:
            PROBE_COUNTS["success"] += 1
        else:
            PROBE_COUNTS["failure"] += 1

    return PROBE_RESULTS

def background_prober_loop():
    """Continuous probe execution loop."""
    time.sleep(2)
    while True:
        try:
            run_all_probes()
        except Exception as e:
            print(f"[Synthetic-Prober] Error executing scheduled probe: {e}", file=sys.stderr)
        time.sleep(PROBE_INTERVAL)

# Start background prober thread
t = threading.Thread(target=background_prober_loop, daemon=True)
t.start()

class SyntheticProberHandler(BaseHTTPRequestHandler):
    def _send_text(self, status: int, text: str, content_type: str = "text/plain"):
        body = text.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def finish(self):
        try:
            super().finish()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        global PROBE_RESULTS, PROBE_COUNTS, SIMULATED_TARGET_FAILURE
        if self.path == "/healthz" or self.path == "/health":
            self._send_text(200, '{"status":"ok","service":"argus-synthetic-prober"}', "application/json")
            return

        if self.path == "/metrics":
            with LOCK:
                res = dict(PROBE_RESULTS)
                counts = dict(PROBE_COUNTS)

            if not res:
                res = run_all_probes()

            lines = [
                "# HELP argus_synthetic_probe_success Synthetic canary probe availability (1 = success, 0 = failure)",
                "# TYPE argus_synthetic_probe_success gauge",
                f'argus_synthetic_probe_success{{target="{res.get("target","sample-service")}",probe_type="{res.get("probe_type","canary")}"}} {res.get("success", 1)}',
                "",
                "# HELP argus_synthetic_probe_duration_seconds Total execution time of synthetic canary probe",
                "# TYPE argus_synthetic_probe_duration_seconds gauge",
                f'argus_synthetic_probe_duration_seconds{{target="{res.get("target","sample-service")}",probe_type="{res.get("probe_type","canary")}"}} {res.get("duration_seconds", 0.0):.4f}',
                "",
                "# HELP argus_synthetic_probe_step_duration_seconds Duration of individual synthetic probe steps",
                "# TYPE argus_synthetic_probe_step_duration_seconds gauge"
            ]

            for s in res.get("steps", []):
                lines.append(f'argus_synthetic_probe_step_duration_seconds{{target="{res.get("target","sample-service")}",step="{s["name"]}"}} {s["duration_seconds"]:.4f}')

            lines.extend([
                "",
                "# HELP argus_synthetic_probes_total Total number of executed synthetic canary probes",
                "# TYPE argus_synthetic_probes_total counter",
                f'argus_synthetic_probes_total{{target="argus-sample-service",status="success"}} {counts.get("success", 0)}',
                f'argus_synthetic_probes_total{{target="argus-sample-service",status="failure"}} {counts.get("failure", 0)}',
                ""
            ])

            self._send_text(200, "\n".join(lines), "text/plain; version=0.0.4")
            return

        if self.path == "/api/status":
            with LOCK:
                data = {
                    "last_probe": PROBE_RESULTS,
                    "counts": PROBE_COUNTS,
                    "simulated_target_failure": SIMULATED_TARGET_FAILURE
                }
            self._send_text(200, json.dumps(data, indent=2), "application/json")
            return

        self._send_text(404, '{"error":"Not Found"}', "application/json")

    def do_POST(self):
        global SIMULATED_TARGET_FAILURE
        auth_ok, auth_code, auth_err = verify_prober_auth(self.headers)
        if not auth_ok:
            self._send_text(auth_code, json.dumps({"error": auth_err}), "application/json")
            return

        if self.path == "/api/run":
            res = run_all_probes()
            self._send_text(200, json.dumps(res, indent=2), "application/json")
            return

        if self.path == "/api/simulate/fail_target":
            with LOCK:
                SIMULATED_TARGET_FAILURE = True
            run_all_probes()
            self._send_text(200, '{"status":"target_failure_simulated"}', "application/json")
            return

        if self.path == "/api/simulate/recover_target":
            with LOCK:
                SIMULATED_TARGET_FAILURE = False
            run_all_probes()
            self._send_text(200, '{"status":"target_recovered"}', "application/json")
            return

        self._send_text(404, '{"error":"Not Found"}', "application/json")

    def log_message(self, format, *args):
        sys.stdout.write(f"[Synthetic-Prober] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

if __name__ == "__main__":
    print(f"Starting Argus Synthetic Canary Prober on port {PORT}...")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), SyntheticProberHandler)
    server.daemon_threads = True
    server.serve_forever()
