#!/usr/bin/env python3
"""
Argus Mock ServiceNow Incident Table API Service
Emulates ServiceNow REST Table API (/api/now/table/incident) for air-gapped testing.
Supports incident creation, updates, state transitions, and simulated outage modes.
"""

import json
import os
import sys
import time
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

PORT = int(os.environ.get("PORT", "8088"))

INCIDENTS = {}
INCIDENT_COUNTER = 10000
LOCK = threading.Lock()
SIMULATE_FAILURE = False

class ServiceNowMockHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        global INCIDENTS, SIMULATE_FAILURE
        if self.path == "/healthz" or self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "argus-servicenow-mock"})
            return

        if self.path.startswith("/api/now/table/incident"):
            with LOCK:
                if SIMULATE_FAILURE:
                    self._send_json(503, {"error": {"message": "ServiceNow instance currently unavailable", "detail": "Node restarting"}})
                    return

                # If specific ID queried: /api/now/table/incident/<sys_id>
                parts = self.path.split("/")
                if len(parts) >= 6 and parts[5]:
                    sys_id = parts[5].split("?")[0]
                    if sys_id in INCIDENTS:
                        self._send_json(200, {"result": INCIDENTS[sys_id]})
                    else:
                        self._send_json(404, {"error": {"message": "Record not found", "detail": sys_id}})
                    return

                # Query all
                results = list(INCIDENTS.values())
                self._send_json(200, {"result": results, "total_records": len(results)})
                return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        global INCIDENTS, INCIDENT_COUNTER, SIMULATE_FAILURE
        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        try:
            req_data = json.loads(raw_body) if raw_body else {}
        except Exception as e:
            self._send_json(400, {"error": {"message": "Invalid JSON body", "detail": str(e)}})
            return

        if self.path == "/api/simulate/fail":
            with LOCK:
                SIMULATE_FAILURE = True
            self._send_json(200, {"status": "failure_mode_enabled", "code": 503})
            return

        if self.path == "/api/simulate/recover":
            with LOCK:
                SIMULATE_FAILURE = False
            self._send_json(200, {"status": "recovered", "code": 200})
            return

        if self.path == "/api/now/table/incident":
            with LOCK:
                if SIMULATE_FAILURE:
                    self._send_json(503, {"error": {"message": "ServiceNow instance currently unavailable (simulated)"}})
                    return

                INCIDENT_COUNTER += 1
                sys_id = secrets.token_hex(16)
                number = f"INC00{INCIDENT_COUNTER}"
                now_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

                record = {
                    "sys_id": sys_id,
                    "number": number,
                    "short_description": req_data.get("short_description", "No summary"),
                    "description": req_data.get("description", ""),
                    "urgency": str(req_data.get("urgency", "2")),
                    "impact": str(req_data.get("impact", "2")),
                    "priority": str(req_data.get("priority", "2")),
                    "category": req_data.get("category", "Monitoring"),
                    "correlation_id": req_data.get("correlation_id", ""),
                    "state": str(req_data.get("state", "1")), # 1 = New
                    "assignment_group": req_data.get("assignment_group", "DHS-Security-Ops"),
                    "opened_at": now_iso,
                    "sys_created_on": now_iso,
                    "sys_updated_on": now_iso,
                    "work_notes": req_data.get("work_notes", "Incident automatically opened by Argus Paging Gateway"),
                    "close_notes": "",
                    "caller_id": req_data.get("caller_id", "argus-monitoring-automation")
                }

                INCIDENTS[sys_id] = record
                self._send_json(201, {"result": record})
                return

        self._send_json(404, {"error": "Not Found"})

    def do_PATCH(self):
        global INCIDENTS, SIMULATE_FAILURE
        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"

        try:
            patch_data = json.loads(raw_body) if raw_body else {}
        except Exception as e:
            self._send_json(400, {"error": {"message": "Invalid JSON body", "detail": str(e)}})
            return

        if self.path.startswith("/api/now/table/incident/"):
            with LOCK:
                if SIMULATE_FAILURE:
                    self._send_json(503, {"error": {"message": "ServiceNow instance currently unavailable (simulated)"}})
                    return

                sys_id = self.path.split("/")[-1].split("?")[0]
                if sys_id not in INCIDENTS:
                    self._send_json(404, {"error": {"message": "Incident not found", "sys_id": sys_id}})
                    return

                rec = INCIDENTS[sys_id]
                now_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
                for k, v in patch_data.items():
                    rec[k] = str(v)
                rec["sys_updated_on"] = now_iso
                if "work_notes" in patch_data:
                    rec["work_notes"] = f"{rec.get('work_notes', '')}\n[{now_iso}] {patch_data['work_notes']}".strip()

                self._send_json(200, {"result": rec})
                return

        self._send_json(404, {"error": "Not Found"})

    def do_DELETE(self):
        global INCIDENTS
        if self.path == "/api/now/table/incident":
            with LOCK:
                count = len(INCIDENTS)
                INCIDENTS.clear()
            self._send_json(200, {"status": "cleared", "deleted_records": count})
            return
        self._send_json(404, {"error": "Not Found"})

    def log_message(self, format, *args):
        # Concise logging to stdout
        sys.stdout.write(f"[ServiceNow-Mock] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

if __name__ == "__main__":
    print(f"Starting Argus Mock ServiceNow Incident Table API Server on port {PORT}...")
    server = HTTPServer(("0.0.0.0", PORT), ServiceNowMockHandler)
    server.serve_forever()
