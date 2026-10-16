#!/usr/bin/env python3
"""
Argus Sample Instrumented Service
Emits correlated OpenTelemetry traces, logs, and metrics for HTTP transactions.
Supports configurable edge case simulation (dropped span, missing trace id, clock skew).
Provides in-service SLO tracking, error budget burndown calculation, and visual dashboard.
"""

import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import secrets
import signal
import threading
from collections import deque

PORT = int(os.environ.get("PORT", "8080"))
OTEL_GATEWAY_URL = os.environ.get(
    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://argus-gateway-collector.argus-system:4318"
).rstrip("/")
PYROSCOPE_SERVER_URL = os.environ.get(
    "PYROSCOPE_SERVER_ADDRESS", "http://pyroscope.argus-system.svc.cluster.local:4040"
).rstrip("/")
PROFILING_ENABLED = os.environ.get("PROFILING_ENABLED", "true").lower() in ("true", "1", "yes")
SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "argus-sample-service")
NAMESPACE = os.environ.get("POD_NAMESPACE", "argus-system")
POD_NAME = os.environ.get("POD_NAME", "sample-service-pod")
NODE_NAME = os.environ.get("NODE_NAME", "docker-desktop")
SLO_TARGET_PERCENT = float(os.environ.get("SLO_TARGET_PERCENT", "99.0"))
SLO_LATENCY_TARGET_MS = float(os.environ.get("SLO_LATENCY_TARGET_MS", "500.0"))
SAMPLE_APP_API_TOKEN = os.environ.get("SAMPLE_APP_API_TOKEN", "")

# Global in-memory storage for received alert webhooks
RECEIVED_ALERTS = []
ALERTS_LOCK = threading.Lock()


def verify_sample_app_auth(headers) -> tuple[bool, int, str]:
    """Authenticates state-changing requests via Authorization: Bearer or X-Argus-Token header."""
    if not SAMPLE_APP_API_TOKEN:
        return False, 500, "Server configuration error: SAMPLE_APP_API_TOKEN is not configured"
    argus_tok = headers.get("X-Argus-Token", "").strip()
    if argus_tok and hmac.compare_digest(argus_tok, SAMPLE_APP_API_TOKEN):
        return True, 200, "OK"
    auth_header = headers.get("Authorization", "").strip()
    if auth_header.startswith("Bearer "):
        bearer_tok = auth_header.split(" ", 1)[1].strip()
        if bearer_tok and hmac.compare_digest(bearer_tok, SAMPLE_APP_API_TOKEN):
            return True, 200, "OK"
    return False, 401, "Unauthorized: valid Bearer or X-Argus-Token required"


class SLOTracker:
    """
    In-memory, thread-safe Service Level Objective (SLO) accountant.
    Calculates Availability SLI, Latency SLI, Error Budget Consumed/Remaining, and Burn Rate.
    """
    def __init__(self, target_slo_percent: float = 99.0, latency_target_ms: float = 500.0, max_events: int = 10000):
        self.target_slo_percent = float(target_slo_percent)
        self.latency_target_ms = float(latency_target_ms)
        self.max_events = max_events
        self.lock = threading.Lock()
        self.events = deque(maxlen=max_events)
        self.total_requests = 0
        self.good_requests = 0
        self.bad_requests = 0
        self.good_latency_requests = 0
        self.bad_latency_requests = 0

    def record(self, status_code: int, duration_ms: float):
        with self.lock:
            self.total_requests += 1
            is_good = status_code < 500
            if is_good:
                self.good_requests += 1
            else:
                self.bad_requests += 1

            is_good_latency = duration_ms <= self.latency_target_ms
            if is_good_latency:
                self.good_latency_requests += 1
            else:
                self.bad_latency_requests += 1

            self.events.append({
                "ts": time.time(),
                "status": status_code,
                "duration_ms": duration_ms,
                "good": is_good,
                "good_latency": is_good_latency
            })

    def reset(self):
        with self.lock:
            self.events.clear()
            self.total_requests = 0
            self.good_requests = 0
            self.bad_requests = 0
            self.good_latency_requests = 0
            self.bad_latency_requests = 0

    def get_status(self) -> dict:
        with self.lock:
            total = self.total_requests
            good = self.good_requests
            bad = self.bad_requests
            good_lat = self.good_latency_requests
            bad_lat = self.bad_latency_requests
            target_slo = self.target_slo_percent
            target_lat = self.latency_target_ms

        error_budget_total = (100.0 - target_slo) / 100.0  # e.g. 0.01 for 99.0%

        if total == 0:
            sli_ratio = 1.0
            sli_percent = 100.0
            error_rate = 0.0
            error_budget_consumed = 0.0
            error_budget_remaining = 100.0
            burn_rate = 0.0
            status = "NO_TRAFFIC"
            burn_rate_alert = "NORMAL"
            latency_sli_ratio = 1.0
            latency_sli_percent = 100.0
        else:
            sli_ratio = good / total
            sli_percent = round(sli_ratio * 100.0, 3)
            error_rate = bad / total
            error_budget_consumed = round((error_rate / error_budget_total) * 100.0, 2)
            error_budget_remaining = round(max(0.0, 100.0 - error_budget_consumed), 2)
            burn_rate = round(error_rate / error_budget_total, 2)

            latency_sli_ratio = good_lat / total
            latency_sli_percent = round(latency_sli_ratio * 100.0, 3)

            if error_budget_remaining <= 0.0:
                status = "BUDGET_EXHAUSTED"
                burn_rate_alert = "CRITICAL_EXHAUSTED"
            elif burn_rate >= 14.4:
                status = "BURNING_FAST"
                burn_rate_alert = "CRITICAL_FAST_BURN"
            elif burn_rate >= 6.0:
                status = "BURNING_SLOW"
                burn_rate_alert = "WARNING_SLOW_BURN"
            else:
                status = "HEALTHY"
                burn_rate_alert = "NORMAL"

        return {
            "service": SERVICE_NAME,
            "window": f"sliding_{self.max_events}",
            "target_slo_percent": target_slo,
            "total_requests": total,
            "good_requests": good,
            "bad_requests": bad,
            "sli_ratio": round(sli_ratio, 5),
            "sli_percent": sli_percent,
            "error_rate_percent": round(error_rate * 100.0, 3),
            "error_budget_consumed_percent": error_budget_consumed,
            "error_budget_remaining_percent": error_budget_remaining,
            "burn_rate": burn_rate,
            "status": status,
            "burn_rate_alert": burn_rate_alert,
            "latency_sli": {
                "target_ms": target_lat,
                "good_requests": good_lat,
                "bad_requests": bad_lat,
                "sli_percent": latency_sli_percent
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }


# Initialize global SLO tracker
slo_tracker = SLOTracker(target_slo_percent=SLO_TARGET_PERCENT, latency_target_ms=SLO_LATENCY_TARGET_MS)


def emit_pyroscope_profile(profile_type: str, stack_data: str, sample_rate: int = 100) -> bool:
    """Post folded stack traces to Pyroscope server /ingest endpoint."""
    if not PROFILING_ENABLED or not PYROSCOPE_SERVER_URL:
        return False
    try:
        now_sec = int(time.time())
        from_sec = now_sec - 10
        if profile_type == "cpu":
            url = f"{PYROSCOPE_SERVER_URL}/ingest?name={SERVICE_NAME}.cpu&from={from_sec}&until={now_sec}&sampleRate={sample_rate}&format=folded"
        elif profile_type in ("memory", "alloc_space"):
            url = f"{PYROSCOPE_SERVER_URL}/ingest?name={SERVICE_NAME}.alloc_space&from={from_sec}&until={now_sec}&format=folded&units=bytes"
        else:
            url = f"{PYROSCOPE_SERVER_URL}/ingest?name={SERVICE_NAME}.{profile_type}&from={from_sec}&until={now_sec}&format=folded"

        data = stack_data.encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "text/plain"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status in (200, 202)
    except Exception as e:
        sys.stderr.write(f"[WARN] Pyroscope profile ingestion to {PYROSCOPE_SERVER_URL} failed: {e}\n")
        return False


def generate_cpu_profile() -> str:
    return (
        f"main;RequestHandler.handle_request;process_order;validate_request 45\n"
        f"main;RequestHandler.handle_request;process_order;db_query 120\n"
        f"main;RequestHandler.handle_request;process_order;crypto_hash 85\n"
        f"main;background_profiler_loop;heartbeat 15"
    )


def generate_memory_profile() -> str:
    return (
        f"main;RequestHandler.handle_request;process_order;allocate_buffer 1048576\n"
        f"main;RequestHandler.handle_request;process_order;cache_map 2097152\n"
        f"main;background_profiler_loop;worker_buffer 524288"
    )


def background_profiler_loop():
    sys.stderr.write(f"Starting continuous profiler background loop (target: {PYROSCOPE_SERVER_URL})...\n")
    while True:
        try:
            if PROFILING_ENABLED and PYROSCOPE_SERVER_URL:
                emit_pyroscope_profile("cpu", generate_cpu_profile())
                emit_pyroscope_profile("memory", generate_memory_profile())
        except Exception as e:
            sys.stderr.write(f"[WARN] Error in background profiler: {e}\n")
        time.sleep(10)


def post_otlp(path: str, payload: dict) -> None:
    """Post JSON payload to OpenTelemetry Collector HTTP receiver."""
    url = f"{OTEL_GATEWAY_URL}/{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        if resp.status not in (200, 202):
            raise RuntimeError(f"OTLP post to {url} returned HTTP {resp.status}")


def emit_trace(
    trace_id: str,
    span_id: str,
    span_name: str,
    start_ns: int,
    end_ns: int,
    order_id: str,
    status_code: int = 200,
) -> None:
    otel_status = {"code": 1} if status_code < 500 else {"code": 2, "message": f"HTTP {status_code} error"}
    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                        {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
                        {"key": "k8s.pod.name", "value": {"stringValue": POD_NAME}},
                        {"key": "k8s.node.name", "value": {"stringValue": NODE_NAME}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "sample.order.processor", "version": "1.0.0"},
                        "spans": [
                            {
                                "traceId": trace_id,
                                "spanId": span_id,
                                "name": span_name,
                                "kind": 1,  # SPAN_KIND_SERVER
                                "startTimeUnixNano": str(start_ns),
                                "endTimeUnixNano": str(end_ns),
                                "attributes": [
                                    {"key": "http.method", "value": {"stringValue": "POST"}},
                                    {"key": "http.target", "value": {"stringValue": "/order"}},
                                    {"key": "http.status_code", "value": {"intValue": str(status_code)}},
                                    {"key": "order.id", "value": {"stringValue": order_id}},
                                    {"key": "order.amount", "value": {"stringValue": "99.99"}},
                                    {"key": "order.currency", "value": {"stringValue": "USD"}},
                                ],
                                "status": otel_status,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    post_otlp("v1/traces", payload)


def emit_log(
    trace_id: str,
    span_id: str,
    log_time_ns: int,
    body: str,
    order_id: str,
    severity: str = "INFO",
) -> None:
    sev_num = 17 if severity == "ERROR" else 9  # 17 = ERROR, 9 = INFO
    log_record = {
        "timeUnixNano": str(log_time_ns),
        "observedTimeUnixNano": str(log_time_ns),
        "severityNumber": sev_num,
        "severityText": severity,
        "body": {"stringValue": body},
        "attributes": [
            {"key": "order.id", "value": {"stringValue": order_id}},
            {"key": "transaction.status", "value": {"stringValue": "FAILED" if severity == "ERROR" else "COMPLETED"}},
        ],
    }
    if trace_id:
        log_record["traceId"] = trace_id
    if span_id:
        log_record["spanId"] = span_id

    payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                        {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
                        {"key": "k8s.pod.name", "value": {"stringValue": POD_NAME}},
                        {"key": "k8s.node.name", "value": {"stringValue": NODE_NAME}},
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {"name": "sample.order.processor", "version": "1.0.0"},
                        "logRecords": [log_record],
                    }
                ],
            }
        ]
    }
    post_otlp("v1/logs", payload)


def emit_metric(
    trace_id: str,
    span_id: str,
    metric_time_ns: int,
    metric_name: str,
    value: float,
    order_id: str,
    is_success: bool = True,
) -> None:
    status_str = "success" if is_success else "error"
    data_point = {
        "timeUnixNano": str(metric_time_ns),
        "asDouble": value,
        "attributes": [
            {"key": "order.id", "value": {"stringValue": order_id}},
            {"key": "trace_id", "value": {"stringValue": trace_id}},
            {"key": "status", "value": {"stringValue": status_str}},
        ],
        "exemplars": [
            {
                "timeUnixNano": str(metric_time_ns),
                "asDouble": value,
                "traceId": trace_id,
                "spanId": span_id,
                "filteredAttributes": [],
            }
        ],
    }

    payload = {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                        {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
                        {"key": "k8s.pod.name", "value": {"stringValue": POD_NAME}},
                        {"key": "k8s.node.name", "value": {"stringValue": NODE_NAME}},
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "sample.order.processor", "version": "1.0.0"},
                        "metrics": [
                            {
                                "name": metric_name,
                                "description": "Order processing transaction duration",
                                "unit": "ms",
                                "gauge": {"dataPoints": [data_point]},
                            }
                        ],
                    }
                ],
            }
        ]
    }
    post_otlp("v1/metrics", payload)


def emit_slo_metrics(status: dict) -> None:
    """Emits OpenTelemetry gauge metrics for SLO SLI ratio, budget remaining, and burn rate."""
    now_ns = int(time.time() * 1e9)
    metrics = [
        {
            "name": "argus_slo_sli_ratio",
            "description": "Current Service Level Indicator availability ratio (0.0 to 1.0)",
            "unit": "1",
            "gauge": {
                "dataPoints": [
                    {
                        "timeUnixNano": str(now_ns),
                        "asDouble": float(status["sli_ratio"]),
                        "attributes": [
                            {"key": "service", "value": {"stringValue": SERVICE_NAME}},
                            {"key": "slo_name", "value": {"stringValue": "availability"}},
                        ],
                    }
                ]
            },
        },
        {
            "name": "argus_slo_error_budget_remaining_percent",
            "description": "Error budget remaining percentage (0.0 to 100.0)",
            "unit": "%",
            "gauge": {
                "dataPoints": [
                    {
                        "timeUnixNano": str(now_ns),
                        "asDouble": float(status["error_budget_remaining_percent"]),
                        "attributes": [
                            {"key": "service", "value": {"stringValue": SERVICE_NAME}},
                            {"key": "slo_name", "value": {"stringValue": "availability"}},
                        ],
                    }
                ]
            },
        },
        {
            "name": "argus_slo_burn_rate",
            "description": "Current error budget burn rate multiplier",
            "unit": "1",
            "gauge": {
                "dataPoints": [
                    {
                        "timeUnixNano": str(now_ns),
                        "asDouble": float(status["burn_rate"]),
                        "attributes": [
                            {"key": "service", "value": {"stringValue": SERVICE_NAME}},
                            {"key": "slo_name", "value": {"stringValue": "availability"}},
                        ],
                    }
                ]
            },
        },
    ]

    payload = {
        "resourceMetrics": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
                        {"key": "service.version", "value": {"stringValue": "1.0.0"}},
                        {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
                    ]
                },
                "scopeMetrics": [
                    {
                        "scope": {"name": "argus.slo.tracker", "version": "1.0.0"},
                        "metrics": metrics,
                    }
                ],
            }
        ]
    }
    try:
        post_otlp("v1/metrics", payload)
    except Exception as e:
        sys.stderr.write(f"[WARN] Non-fatal SLO metric emission error: {e}\n")


def render_slo_html(status: dict) -> str:
    """Renders a self-contained, air-gapped HTML dashboard for the SLO and Error Budget tracker."""
    status_str = status.get("status", "HEALTHY")
    if status_str == "HEALTHY":
        badge_bg = "#064e3b"
        badge_color = "#34d399"
        badge_border = "#059669"
    elif status_str in ("BURNING_FAST", "BUDGET_EXHAUSTED"):
        badge_bg = "#7f1d1d"
        badge_color = "#f87171"
        badge_border = "#dc2626"
    elif status_str == "BURNING_SLOW":
        badge_bg = "#78350f"
        badge_color = "#fbbf24"
        badge_border = "#d97706"
    else:  # NO_TRAFFIC
        badge_bg = "#1e293b"
        badge_color = "#94a3b8"
        badge_border = "#475569"

    budget_rem = float(status.get("error_budget_remaining_percent", 100.0))
    if budget_rem >= 50.0:
        bar_color = "linear-gradient(90deg, #10b981 0%, #34d399 100%)"
    elif budget_rem >= 10.0:
        bar_color = "linear-gradient(90deg, #f59e0b 0%, #fbbf24 100%)"
    else:
        bar_color = "linear-gradient(90deg, #ef4444 0%, #f87171 100%)"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Argus // SLO & Error Budget Tracker</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      background: #090d16;
      color: #f1f5f9;
      padding: 24px;
      line-height: 1.5;
    }}
    .container {{
      max-width: 960px;
      margin: 0 auto;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding-bottom: 20px;
      border-bottom: 1px solid #1e293b;
      margin-bottom: 24px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .logo-badge {{
      background: #0284c7;
      color: #fff;
      font-weight: 700;
      font-size: 13px;
      padding: 4px 8px;
      border-radius: 4px;
      letter-spacing: 0.05em;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 600;
      color: #f8fafc;
    }}
    .subtitle {{
      font-size: 13px;
      color: #94a3b8;
    }}
    .badge {{
      font-size: 12px;
      font-weight: 600;
      padding: 6px 14px;
      border-radius: 9999px;
      background: {badge_bg};
      color: {badge_color};
      border: 1px solid {badge_border};
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .card {{
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 16px 20px;
    }}
    .card-label {{
      font-size: 12px;
      font-weight: 500;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .card-value {{
      font-size: 26px;
      font-weight: 700;
      color: #f8fafc;
    }}
    .card-value.accent {{
      color: #38bdf8;
    }}
    .card-subtext {{
      font-size: 12px;
      color: #64748b;
      margin-top: 4px;
    }}
    .burndown-card {{
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .burndown-header {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
    }}
    .burndown-title {{
      font-size: 14px;
      font-weight: 600;
      color: #e2e8f0;
    }}
    .burndown-stats {{
      font-size: 13px;
      font-weight: 500;
      color: #38bdf8;
    }}
    .progress-track {{
      background: #1e293b;
      height: 20px;
      border-radius: 10px;
      overflow: hidden;
      position: relative;
    }}
    .progress-fill {{
      height: 100%;
      width: {min(100.0, max(0.0, budget_rem))}%;
      background: {bar_color};
      transition: width 0.3s ease;
    }}
    .details-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 12px;
    }}
    .details-table th, .details-table td {{
      padding: 10px 14px;
      text-align: left;
      font-size: 13px;
    }}
    .details-table th {{
      background: #1f2937;
      color: #94a3b8;
      font-weight: 500;
      border-bottom: 1px solid #374151;
    }}
    .details-table td {{
      border-bottom: 1px solid #1e293b;
      color: #e2e8f0;
    }}
    .details-table tr:hover {{
      background: #1a2234;
    }}
    .actions {{
      display: flex;
      gap: 12px;
      margin-top: 24px;
      justify-content: flex-end;
    }}
    .btn {{
      padding: 8px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid transparent;
    }}
    .btn-primary {{
      background: #0284c7;
      color: #fff;
    }}
    .btn-primary:hover {{
      background: #0369a1;
    }}
    .btn-secondary {{
      background: #1e293b;
      color: #e2e8f0;
      border-color: #334155;
    }}
    .btn-secondary:hover {{
      background: #334155;
    }}
    .footer {{
      margin-top: 32px;
      text-align: center;
      font-size: 12px;
      color: #64748b;
      border-top: 1px solid #1e293b;
      padding-top: 16px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div class="brand">
        <span class="logo-badge">ARGUS</span>
        <div>
          <h1>Service Level Objective (SLO)</h1>
          <div class="subtitle">{status.get("service", "argus-sample-service")} • Window: {status.get("window", "sliding_10000")}</div>
        </div>
      </div>
      <span class="badge" id="slo-status-badge">{status_str}</span>
    </div>

    <div class="grid">
      <div class="card">
        <div class="card-label">SLO Objective Target</div>
        <div class="card-value">{status.get("target_slo_percent", 99.0):.2f}%</div>
        <div class="card-subtext">Allowable Error Rate: {100.0 - float(status.get("target_slo_percent", 99.0)):.2f}%</div>
      </div>
      <div class="card">
        <div class="card-label">Current Availability SLI</div>
        <div class="card-value accent">{status.get("sli_percent", 100.0):.2f}%</div>
        <div class="card-subtext">Ratio: {status.get("sli_ratio", 1.0):.4f}</div>
      </div>
      <div class="card">
        <div class="card-label">Error Budget Remaining</div>
        <div class="card-value" style="color: {badge_color};">{status.get("error_budget_remaining_percent", 100.0):.1f}%</div>
        <div class="card-subtext">Consumed: {status.get("error_budget_consumed_percent", 0.0):.1f}%</div>
      </div>
      <div class="card">
        <div class="card-label">Current Burn Rate</div>
        <div class="card-value">{status.get("burn_rate", 0.0):.2f}x</div>
        <div class="card-subtext">Alert State: {status.get("burn_rate_alert", "NORMAL")}</div>
      </div>
    </div>

    <div class="burndown-card">
      <div class="burndown-header">
        <span class="burndown-title">Error Budget Burndown</span>
        <span class="burndown-stats">{budget_rem:.1f}% Available / {status.get("error_budget_consumed_percent", 0.0):.1f}% Consumed</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" id="budget-progress-bar"></div>
      </div>
    </div>

    <div class="card">
      <div class="card-label">Telemetry & SLI Breakdown</div>
      <table class="details-table">
        <thead>
          <tr>
            <th>Metric / Dimension</th>
            <th>Value</th>
            <th>Target / Threshold</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Total Evaluated Requests</td>
            <td><strong>{status.get("total_requests", 0)}</strong></td>
            <td>&mdash;</td>
            <td>Captured</td>
          </tr>
          <tr>
            <td>Good Requests (Status &lt; 500)</td>
            <td><strong>{status.get("good_requests", 0)}</strong></td>
            <td>&ge; 99.0%</td>
            <td style="color: #34d399;">Passing</td>
          </tr>
          <tr>
            <td>Bad Requests (Status &ge; 500)</td>
            <td><strong>{status.get("bad_requests", 0)}</strong></td>
            <td>&le; 1.0%</td>
            <td style="color: {'#f87171' if status.get('bad_requests', 0) > 0 else '#94a3b8'};">
              {status.get("error_rate_percent", 0.0):.2f}% error rate
            </td>
          </tr>
          <tr>
            <td>Latency SLI (Duration &le; {status.get('latency_sli', {}).get('target_ms', 500):.0f}ms)</td>
            <td><strong>{status.get('latency_sli', {}).get('sli_percent', 100.0):.1f}%</strong></td>
            <td>&ge; 95.0%</td>
            <td style="color: {'#34d399' if status.get('latency_sli', {}).get('sli_percent', 100.0) >= 95.0 else '#f87171'};">
              {status.get('latency_sli', {}).get('good_requests', 0)} / {status.get('total_requests', 0)}
            </td>
          </tr>
          <tr>
            <td>Fast Burn Rate Alert Threshold</td>
            <td><strong>14.4x</strong> (2% in 1h)</td>
            <td>Critical Alert</td>
            <td style="color: {'#f87171' if status.get('burn_rate', 0.0) >= 14.4 else '#94a3b8'};">
              {'TRIGGERED' if status.get('burn_rate', 0.0) >= 14.4 else 'OK'}
            </td>
          </tr>
          <tr>
            <td>Slow Burn Rate Alert Threshold</td>
            <td><strong>6.0x</strong> (5% in 6h)</td>
            <td>Warning Alert</td>
            <td style="color: {'#fbbf24' if status.get('burn_rate', 0.0) >= 6.0 else '#94a3b8'};">
              {'TRIGGERED' if status.get('burn_rate', 0.0) >= 6.0 else 'OK'}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="actions">
      <button class="btn btn-secondary" onclick="window.location.reload()">Refresh Metrics</button>
      <button class="btn btn-primary" onclick="resetSLO()">Reset Error Budget</button>
    </div>

    <div class="footer">
      Project Argus SRE Suite • Air-Gapped Internal Platform • Refreshed at {status.get("timestamp", "")}
    </div>
  </div>

  <script>
    function resetSLO() {{
      if (confirm("Reset error budget and request counters to baseline?")) {{
        fetch("/api/slo/reset", {{ method: "POST" }})
          .then(() => window.location.reload())
          .catch(err => alert("Reset failed: " + err));
      }}
    }}
  </script>
</body>
</html>"""
    return html


class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet stdout logging in container
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def handle_request(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy"}')
            return

        # SLO JSON Status endpoint
        if path == "/api/slo":
            status = slo_tracker.get_status()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(status).encode("utf-8"))
            return

        # SLO Reset endpoint
        if path == "/api/slo/reset":
            if self.command != "POST":
                self.send_response(405)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error": "Method Not Allowed"}')
                return
            auth_ok, auth_code, auth_err = verify_sample_app_auth(self.headers)
            if not auth_ok:
                self.send_response(auth_code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": auth_err}).encode("utf-8"))
                return
            slo_tracker.reset()
            status = slo_tracker.get_status()
            emit_slo_metrics(status)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "reset", "slo": status}).encode("utf-8"))
            return

        # Visual SLO Dashboard
        if path in ("/slo", "/slo/dashboard"):
            status = slo_tracker.get_status()
            html = render_slo_html(status)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))
            return

        # Webhook Alert Ingestion & Query endpoint
        if path == "/api/alerts":
            if self.command == "POST":
                auth_ok, auth_code, auth_err = verify_sample_app_auth(self.headers)
                if not auth_ok:
                    self.send_response(auth_code)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": auth_err}).encode("utf-8"))
                    return
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
                try:
                    alert_json = json.loads(body)
                except Exception:
                    alert_json = {"raw": body}
                with ALERTS_LOCK:
                    RECEIVED_ALERTS.append({"time": time.time(), "payload": alert_json})
                    if len(RECEIVED_ALERTS) > 50:
                        RECEIVED_ALERTS.pop(0)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "received"}')
                return
            else:
                with ALERTS_LOCK:
                    alerts_copy = list(RECEIVED_ALERTS)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"alerts": alerts_copy}).encode("utf-8"))
                return

        if path in ("/order", "/api/order"):
            # Edge case flags
            drop_span = query.get("drop_span", ["false"])[0].lower() in ("true", "1")
            no_trace_id = query.get("no_trace_id", ["false"])[0].lower() in ("true", "1")
            skew_seconds = int(query.get("skew_seconds", ["0"])[0])
            order_id = query.get("order_id", [f"order-{secrets.token_hex(4)}"])[0]

            # SLO control flags
            fail_param = query.get("fail", ["false"])[0].lower() in ("true", "1")
            explicit_status = int(query.get("status_code", [0])[0])
            simulated_latency = float(query.get("latency_ms", [45.2])[0])

            # Determine response status code
            if explicit_status > 0:
                target_status = explicit_status
            elif fail_param:
                target_status = 500
            else:
                target_status = 200

            # Generate W3C TraceContext
            trace_id = secrets.token_hex(16)  # 32 hex chars
            span_id = secrets.token_hex(8)    # 16 hex chars

            # Timestamp calculation
            now_ns = int(time.time() * 1e9) + (skew_seconds * 1_000_000_000)
            start_ns = now_ns
            duration_ns = int(simulated_latency * 1_000_000)
            end_ns = now_ns + duration_ns
            metric_val = simulated_latency

            is_success = target_status < 500
            severity = "INFO" if is_success else "ERROR"
            log_body = (
                f"Order {order_id} processed successfully for transaction {trace_id}"
                if is_success
                else f"Order {order_id} failed with HTTP {target_status} for transaction {trace_id}"
            )
            metric_name = "sample_order_duration_ms"

            errors = []

            # 1. Emit trace
            if not drop_span:
                try:
                    emit_trace(
                        trace_id=trace_id,
                        span_id=span_id,
                        span_name="process_order",
                        start_ns=start_ns,
                        end_ns=end_ns,
                        order_id=order_id,
                        status_code=target_status,
                    )
                except Exception as e:
                    errors.append(f"emit_trace: {str(e)}")

            # 2. Emit log
            try:
                emit_log(
                    trace_id="" if no_trace_id else trace_id,
                    span_id="" if no_trace_id else span_id,
                    log_time_ns=start_ns + 20_000_000,
                    body=log_body,
                    order_id=order_id,
                    severity=severity,
                )
            except Exception as e:
                errors.append(f"emit_log: {str(e)}")

            # 3. Emit metric
            try:
                emit_metric(
                    trace_id=trace_id,
                    span_id=span_id,
                    metric_time_ns=end_ns,
                    metric_name=metric_name,
                    value=metric_val,
                    order_id=order_id,
                    is_success=is_success,
                )
            except Exception as e:
                errors.append(f"emit_metric: {str(e)}")

            # 4. Emit profiling data
            if PROFILING_ENABLED:
                try:
                    emit_pyroscope_profile("cpu", generate_cpu_profile())
                    emit_pyroscope_profile("memory", generate_memory_profile())
                except Exception as e:
                    sys.stderr.write(f"[WARN] Non-fatal order profiling error: {e}\n")

            # 5. Record event in SLO Tracker and emit updated SLO metrics
            slo_tracker.record(target_status, simulated_latency)
            current_slo = slo_tracker.get_status()
            emit_slo_metrics(current_slo)

            final_status = target_status if not errors else 500
            resp_data = {
                "status": "partial_error" if errors else ("error" if not is_success else "success"),
                "order_id": order_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "metric_name": metric_name,
                "metric_value": metric_val,
                "log_body": log_body,
                "status_code": target_status,
                "drop_span": drop_span,
                "no_trace_id": no_trace_id,
                "skew_seconds": skew_seconds,
                "errors": errors,
                "slo": {
                    "sli_percent": current_slo["sli_percent"],
                    "error_budget_remaining_percent": current_slo["error_budget_remaining_percent"],
                    "burn_rate": current_slo["burn_rate"],
                    "status": current_slo["status"],
                },
            }

            self.send_response(final_status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            return

        if path == "/api/profile":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "profiling_enabled": PROFILING_ENABLED,
                "pyroscope_server": PYROSCOPE_SERVER_URL,
                "service_name": SERVICE_NAME,
                "status": "active" if PROFILING_ENABLED else "disabled"
            }).encode("utf-8"))
            return

        if path in ("/api/profile/trigger", "/profile/trigger"):
            cpu_ok = emit_pyroscope_profile("cpu", generate_cpu_profile())
            mem_ok = emit_pyroscope_profile("memory", generate_memory_profile())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "triggered",
                "cpu_emitted": cpu_ok,
                "memory_emitted": mem_ok,
                "profiling_enabled": PROFILING_ENABLED
            }).encode("utf-8"))
            return

        # Not found
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error": "not found"}')


def run():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, RequestHandler)

    def handle_shutdown(signum, frame):
        sys.stderr.write(f"Received signal {signum}, shutting down immediately...\n")
        try:
            httpd.server_close()
        except Exception:
            pass
        os._exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    if PROFILING_ENABLED and PYROSCOPE_SERVER_URL:
        profiler_thread = threading.Thread(target=background_profiler_loop, daemon=True)
        profiler_thread.start()

    sys.stderr.write(f"Argus sample service listening on port {PORT} (SLO Target: {SLO_TARGET_PERCENT}%)...\n")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
