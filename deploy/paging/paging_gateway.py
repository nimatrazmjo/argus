#!/usr/bin/env python3
"""
Argus Paging Gateway & Incident Routing Dispatcher
Translates Prometheus Alertmanager / SigNoz Ruler alert notifications into ServiceNow Incident Table API payloads.
Provides duplicate alert suppression, state synchronization (firing -> New, resolved -> Resolved),
and an asynchronous exponential-backoff retry queue for destination resilience during network outages.
"""

import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from queue import Queue, Empty

PORT = int(os.environ.get("PORT", "9099"))
SERVICENOW_URL = os.environ.get(
    "SERVICENOW_URL", "http://argus-servicenow-mock.argus-system.svc.cluster.local:8088/api/now/table/incident"
).rstrip("/")
DEDUP_WINDOW_SECONDS = int(os.environ.get("DEDUP_WINDOW_SECONDS", "300"))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "5"))
PAGING_WEBHOOK_TOKEN = os.environ.get("PAGING_WEBHOOK_TOKEN", "")


def verify_paging_auth(headers) -> tuple[bool, int, str]:
    """Authenticates state-changing requests via X-Webhook-Token or Authorization: Bearer header."""
    if not PAGING_WEBHOOK_TOKEN:
        return False, 500, "Server configuration error: PAGING_WEBHOOK_TOKEN is not configured"
    webhook_token = headers.get("X-Webhook-Token", "").strip()
    if webhook_token and hmac.compare_digest(webhook_token, PAGING_WEBHOOK_TOKEN):
        return True, 200, "OK"
    auth_header = headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        bearer_token = auth_header.split(" ", 1)[1].strip()
        if bearer_token and hmac.compare_digest(bearer_token, PAGING_WEBHOOK_TOKEN):
            return True, 200, "OK"
    return False, 401, "Unauthorized: valid X-Webhook-Token or Bearer token required"

# Global thread-safe state
LOCK = threading.Lock()
ACTIVE_INCIDENTS = {} # fingerprint -> {sys_id, number, state, last_seen, alertname}
STATS = {
    "alerts_received": 0,
    "incidents_created": 0,
    "incidents_resolved": 0,
    "duplicates_suppressed": 0,
    "retries_attempted": 0,
    "retries_succeeded": 0,
    "dispatches_failed": 0
}

RETRY_QUEUE = Queue()

def map_alert_to_servicenow(alert: dict) -> dict:
    """Maps Alertmanager alert JSON structure to ServiceNow Table API Incident fields."""
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    alertname = labels.get("alertname", "UnknownAlert")
    severity = labels.get("severity", "warning").lower()
    service = labels.get("service", labels.get("job", "platform"))
    summary = annotations.get("summary", f"{alertname} on {service}")
    description = annotations.get("description", f"Alert {alertname} fired for service {service}")
    fingerprint = alert.get("fingerprint", "")
    if not fingerprint:
        import hashlib
        fingerprint = hashlib.sha256(f"{alertname}:{service}:{labels}".encode()).hexdigest()[:16]

    # ServiceNow Urgency / Impact mapping:
    # 1 = High, 2 = Medium, 3 = Low
    if severity == "critical":
        urgency = "1"
        impact = "1"
        priority = "1"
    elif severity == "warning":
        urgency = "2"
        impact = "2"
        priority = "2"
    else:
        urgency = "3"
        impact = "3"
        priority = "3"

    return {
        "short_description": f"[ARGUS] {summary}",
        "description": f"Alert: {alertname}\nService: {service}\nSeverity: {severity}\nFingerprint: {fingerprint}\nDetails: {description}\nLabels: {json.dumps(labels)}",
        "urgency": urgency,
        "impact": impact,
        "priority": priority,
        "category": "Infrastructure" if "node" in labels or "kube" in labels else "Application",
        "correlation_id": fingerprint,
        "state": "1", # New
        "assignment_group": "DHS-Argus-SRE",
        "work_notes": f"Incident triggered by Argus Alertmanager. StartsAt: {alert.get('startsAt', '')}"
    }

def send_to_servicenow(payload: dict, method: str = "POST", url: str = None) -> tuple[bool, dict]:
    """Issues an HTTP request to ServiceNow Table API endpoint."""
    target_url = url or SERVICENOW_URL
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        target_url,
        data=body_bytes,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="replace")
        return False, {"error": f"HTTP {e.code}", "detail": err_msg}
    except Exception as e:
        return False, {"error": "ConnectionError", "detail": str(e)}

def retry_worker():
    """Background worker draining retry queue with exponential backoff."""
    while True:
        try:
            task = RETRY_QUEUE.get(timeout=1)
        except Empty:
            continue

        item_type = task["type"] # "create" or "resolve"
        fingerprint = task["fingerprint"]
        payload = task["payload"]
        attempt = task.get("attempt", 0) + 1
        method = task.get("method", "POST")
        url = task.get("url", SERVICENOW_URL)

        with LOCK:
            STATS["retries_attempted"] += 1

        backoff = min(1.0 * (2 ** (attempt - 1)), 15.0)
        time.sleep(backoff)

        success, res = send_to_servicenow(payload, method=method, url=url)
        if success:
            with LOCK:
                STATS["retries_succeeded"] += 1
                if item_type == "create":
                    rec = res.get("result", {})
                    ACTIVE_INCIDENTS[fingerprint] = {
                        "sys_id": rec.get("sys_id", ""),
                        "number": rec.get("number", ""),
                        "state": rec.get("state", "1"),
                        "last_seen": time.time(),
                        "alertname": payload.get("short_description", "")
                    }
                    STATS["incidents_created"] += 1
                elif item_type == "resolve":
                    if fingerprint in ACTIVE_INCIDENTS:
                        ACTIVE_INCIDENTS[fingerprint]["state"] = "6"
                    STATS["incidents_resolved"] += 1
            print(f"[Paging-Gateway Worker] Successfully delivered queued task {item_type} for {fingerprint} on attempt {attempt}")
            RETRY_QUEUE.task_done()
        else:
            if attempt < MAX_RETRIES:
                task["attempt"] = attempt
                RETRY_QUEUE.put(task)
                RETRY_QUEUE.task_done()
                print(f"[Paging-Gateway Worker] Retry failed for {fingerprint} (attempt {attempt}/{MAX_RETRIES}), re-queueing...")
            else:
                with LOCK:
                    STATS["dispatches_failed"] += 1
                RETRY_QUEUE.task_done()
                print(f"[Paging-Gateway Worker] ERROR: Exhausted max retries ({MAX_RETRIES}) for {fingerprint}. Dropping task.")

# Start background retry worker thread
worker_thread = threading.Thread(target=retry_worker, daemon=True)
worker_thread.start()

class PagingGatewayHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        global ACTIVE_INCIDENTS, STATS
        if self.path == "/healthz" or self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "argus-paging-gateway"})
            return

        if self.path == "/api/status":
            with LOCK:
                queue_size = RETRY_QUEUE.qsize()
                data = {
                    "status": "healthy",
                    "active_incidents_count": len(ACTIVE_INCIDENTS),
                    "retry_queue_size": queue_size,
                    "stats": dict(STATS)
                }
            self._send_json(200, data)
            return

        if self.path == "/api/incidents":
            with LOCK:
                copy_incidents = dict(ACTIVE_INCIDENTS)
            self._send_json(200, {"incidents": copy_incidents})
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        global ACTIVE_INCIDENTS, STATS
        auth_ok, auth_code, auth_err = verify_paging_auth(self.headers)
        if not auth_ok:
            self._send_json(auth_code, {"error": auth_err})
            return

        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else ""

        if self.path == "/api/reset":
            with LOCK:
                ACTIVE_INCIDENTS.clear()
                for k in STATS:
                    STATS[k] = 0
            self._send_json(200, {"status": "reset_complete"})
            return

        if self.path == "/webhook/alert":
            if not raw_body:
                self._send_json(400, {"error": "Empty body"})
                return

            try:
                alertmanager_data = json.loads(raw_body)
            except Exception as e:
                self._send_json(400, {"error": f"Invalid JSON payload: {str(e)}"})
                return

            alerts = alertmanager_data.get("alerts", [])
            if not alerts and "status" in alertmanager_data and "labels" in alertmanager_data:
                # Support single-alert structure
                alerts = [alertmanager_data]

            processed_results = []
            now = time.time()

            for alert in alerts:
                status = alert.get("status", "firing").lower()
                fingerprint = alert.get("fingerprint", "")
                labels = alert.get("labels", {})
                if not fingerprint:
                    import hashlib
                    fingerprint = hashlib.sha256(f"{labels.get('alertname','')}:{labels}".encode()).hexdigest()[:16]

                with LOCK:
                    STATS["alerts_received"] += 1

                if status == "firing":
                    # Check Duplicate Suppression Window
                    with LOCK:
                        if fingerprint in ACTIVE_INCIDENTS:
                            prev_incident = ACTIVE_INCIDENTS[fingerprint]
                            # If still in firing/open state and within dedup window
                            if prev_incident.get("state") in ("1", "2"):
                                time_since = now - prev_incident.get("last_seen", 0)
                                if time_since < DEDUP_WINDOW_SECONDS:
                                    STATS["duplicates_suppressed"] += 1
                                    prev_incident["last_seen"] = now
                                    processed_results.append({
                                        "fingerprint": fingerprint,
                                        "action": "suppressed_duplicate",
                                        "existing_ticket": prev_incident.get("number")
                                    })
                                    continue

                    # New incident required
                    sn_payload = map_alert_to_servicenow(alert)
                    success, res = send_to_servicenow(sn_payload, method="POST")
                    if success:
                        rec = res.get("result", {})
                        sys_id = rec.get("sys_id", "")
                        number = rec.get("number", "")
                        with LOCK:
                            ACTIVE_INCIDENTS[fingerprint] = {
                                "sys_id": sys_id,
                                "number": number,
                                "state": "1",
                                "last_seen": now,
                                "alertname": sn_payload.get("short_description")
                            }
                            STATS["incidents_created"] += 1
                        processed_results.append({
                            "fingerprint": fingerprint,
                            "action": "incident_created",
                            "number": number,
                            "sys_id": sys_id
                        })
                    else:
                        # Destination failed -> enqueue for background retry
                        print(f"[Paging-Gateway] ServiceNow dispatch failed for {fingerprint}: {res}. Enqueueing retry task.")
                        RETRY_QUEUE.put({
                            "type": "create",
                            "fingerprint": fingerprint,
                            "payload": sn_payload,
                            "attempt": 0,
                            "method": "POST",
                            "url": SERVICENOW_URL
                        })
                        processed_results.append({
                            "fingerprint": fingerprint,
                            "action": "queued_for_retry",
                            "reason": res.get("error", "DispatchFailed")
                        })

                elif status == "resolved":
                    # Alert resolved -> update ServiceNow incident to Resolved (state=6)
                    with LOCK:
                        if fingerprint in ACTIVE_INCIDENTS:
                            inc_info = ACTIVE_INCIDENTS[fingerprint]
                            sys_id = inc_info.get("sys_id")
                        else:
                            inc_info = None
                            sys_id = None

                    if sys_id:
                        patch_payload = {
                            "state": "6", # Resolved
                            "close_notes": f"Alert cleared by Argus Alertmanager at {alert.get('endsAt', time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime()))}",
                            "work_notes": "Alert condition returned to normal threshold. Ticket marked Resolved automatically."
                        }
                        patch_url = f"{SERVICENOW_URL}/{sys_id}"
                        success, res = send_to_servicenow(patch_payload, method="PATCH", url=patch_url)
                        if success:
                            with LOCK:
                                inc_info["state"] = "6"
                                STATS["incidents_resolved"] += 1
                            processed_results.append({
                                "fingerprint": fingerprint,
                                "action": "incident_resolved",
                                "number": inc_info.get("number"),
                                "sys_id": sys_id
                            })
                        else:
                            print(f"[Paging-Gateway] ServiceNow incident update failed for {sys_id}: {res}. Enqueueing retry.")
                            RETRY_QUEUE.put({
                                "type": "resolve",
                                "fingerprint": fingerprint,
                                "payload": patch_payload,
                                "attempt": 0,
                                "method": "PATCH",
                                "url": patch_url
                            })
                            processed_results.append({
                                "fingerprint": fingerprint,
                                "action": "resolve_queued_for_retry"
                            })
                    else:
                        processed_results.append({
                            "fingerprint": fingerprint,
                            "action": "resolved_ignored_no_prior_incident"
                        })

            self._send_json(200, {
                "status": "success",
                "processed_count": len(processed_results),
                "results": processed_results
            })
            return

        self._send_json(404, {"error": "Not Found"})

    def log_message(self, format, *args):
        sys.stdout.write(f"[Paging-Gateway] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

if __name__ == "__main__":
    print(f"Starting Argus Paging Gateway & Incident Dispatcher on port {PORT}...")
    print(f"Destination ServiceNow URL: {SERVICENOW_URL}")
    server = HTTPServer(("0.0.0.0", PORT), PagingGatewayHandler)
    server.serve_forever()
