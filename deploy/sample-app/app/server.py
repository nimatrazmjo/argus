#!/usr/bin/env python3
"""
Argus Sample Instrumented Service
Emits correlated OpenTelemetry traces, logs, and metrics for HTTP transactions.
Supports configurable edge case simulation (dropped span, missing trace id, clock skew).
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import secrets
import signal

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
) -> None:
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
                                    {"key": "order.id", "value": {"stringValue": order_id}},
                                    {"key": "order.amount", "value": {"stringValue": "99.99"}},
                                    {"key": "order.currency", "value": {"stringValue": "USD"}},
                                ],
                                "status": {"code": 1},  # STATUS_CODE_OK
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
    log_record = {
        "timeUnixNano": str(log_time_ns),
        "observedTimeUnixNano": str(log_time_ns),
        "severityNumber": 9,  # SEVERITY_NUMBER_INFO
        "severityText": severity,
        "body": {"stringValue": body},
        "attributes": [
            {"key": "order.id", "value": {"stringValue": order_id}},
            {"key": "transaction.status", "value": {"stringValue": "COMPLETED"}},
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
) -> None:
    data_point = {
        "timeUnixNano": str(metric_time_ns),
        "asDouble": value,
        "attributes": [
            {"key": "order.id", "value": {"stringValue": order_id}},
            {"key": "trace_id", "value": {"stringValue": trace_id}},
            {"key": "status", "value": {"stringValue": "success"}},
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

        if path in ("/order", "/api/order"):
            # Edge case flags
            drop_span = query.get("drop_span", ["false"])[0].lower() in ("true", "1")
            no_trace_id = query.get("no_trace_id", ["false"])[0].lower() in ("true", "1")
            skew_seconds = int(query.get("skew_seconds", ["0"])[0])
            order_id = query.get("order_id", [f"order-{secrets.token_hex(4)}"])[0]

            # Generate W3C TraceContext
            trace_id = secrets.token_hex(16)  # 32 hex chars
            span_id = secrets.token_hex(8)    # 16 hex chars

            # Timestamp calculation
            now_ns = int(time.time() * 1e9) + (skew_seconds * 1_000_000_000)
            start_ns = now_ns
            end_ns = now_ns + 45_000_000  # 45ms duration
            metric_val = 45.2

            log_body = f"Order {order_id} processed successfully for transaction {trace_id}"
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

            status_code = 500 if errors else 200
            resp_data = {
                "status": "partial_error" if errors else "success",
                "order_id": order_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "metric_name": metric_name,
                "metric_value": metric_val,
                "log_body": log_body,
                "drop_span": drop_span,
                "no_trace_id": no_trace_id,
                "skew_seconds": skew_seconds,
                "errors": errors,
            }

            self.send_response(status_code)
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
        import threading
        profiler_thread = threading.Thread(target=background_profiler_loop, daemon=True)
        profiler_thread.start()

    sys.stderr.write(f"Argus sample service listening on port {PORT}...\n")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
