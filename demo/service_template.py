#!/usr/bin/env python3
"""
Argus 10-Service Datadog-Emulating Microservice Platform
Behaves exactly like Datadog:
- Structured JSON logging with full trace-log correlation (trace_id, span_id, dd.trace_id, dd.span_id)
- Standard Datadog reserved attributes (timestamp, status, service, env, version, ddsource, ddtags)
- Exhaustive step logging (ingress, auth, db query, cache lookup, business logic, downstream RPC, egress, error)
- W3C traceparent propagation & OpenTelemetry OTLP trace & log emission
- Prometheus-compatible metrics exposition on /metrics
- Healthcheck on /healthz
"""

import os
import sys
import json
import time
import uuid
import socket
import threading
import traceback
import urllib.request
import urllib.error
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

SERVICE_NAME = os.environ.get("SERVICE_NAME", "argus-svc-generic")
SERVICE_ROLE = os.environ.get("SERVICE_ROLE", "generic")
PORT = int(os.environ.get("PORT", "8080"))
ENV = os.environ.get("ENV", "production")
VERSION = os.environ.get("VERSION", "1.0.0")
DATACENTER = os.environ.get("DATACENTER", "us-gov-west-1")
OTEL_GATEWAY_URL = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://argus-gateway-collector.argus-system:4318").rstrip("/")
POD_NAME = os.environ.get("POD_NAME", socket.gethostname())
NODE_NAME = os.environ.get("NODE_NAME", "cluster-node")
NAMESPACE = os.environ.get("POD_NAMESPACE", "argus-system")

# Service Map for Inter-Service Calling
DOWNSTREAM_MAP = {
    "auth": os.environ.get("URL_AUTH", "http://argus-svc-auth:8002"),
    "catalog": os.environ.get("URL_CATALOG", "http://argus-svc-catalog:8003"),
    "order": os.environ.get("URL_ORDER", "http://argus-svc-order:8004"),
    "inventory": os.environ.get("URL_INVENTORY", "http://argus-svc-inventory:8005"),
    "payment": os.environ.get("URL_PAYMENT", "http://argus-svc-payment:8006"),
    "billing": os.environ.get("URL_BILLING", "http://argus-svc-billing:8007"),
    "shipping": os.environ.get("URL_SHIPPING", "http://argus-svc-shipping:8008"),
    "notification": os.environ.get("URL_NOTIFICATION", "http://argus-svc-notification:8009"),
    "recommendation": os.environ.get("URL_RECOMMENDATION", "http://argus-svc-recommendation:8010"),
}

# In-memory metrics
METRICS_LOCK = threading.Lock()
HTTP_REQUESTS_TOTAL = {}  # (method, route, status) -> count
HTTP_DURATION_SUM = {}    # route -> sum_seconds
HTTP_DURATION_COUNT = {}  # route -> count
DB_QUERIES_TOTAL = 0
ERRORS_TOTAL = {}         # error_kind -> count

def record_metric_request(method: str, route: str, status: int, duration_s: float):
    key = (method, route, str(status))
    with METRICS_LOCK:
        HTTP_REQUESTS_TOTAL[key] = HTTP_REQUESTS_TOTAL.get(key, 0) + 1
        HTTP_DURATION_SUM[route] = HTTP_DURATION_SUM.get(route, 0.0) + duration_s
        HTTP_DURATION_COUNT[route] = HTTP_DURATION_COUNT.get(route, 0) + 1

def record_metric_db_query():
    global DB_QUERIES_TOTAL
    with METRICS_LOCK:
        DB_QUERIES_TOTAL += 1

def record_metric_error(error_kind: str):
    with METRICS_LOCK:
        ERRORS_TOTAL[error_kind] = ERRORS_TOTAL.get(error_kind, 0) + 1


def trace_id_to_dd_ids(trace_id_hex: str, span_id_hex: str):
    """Convert 128-bit trace ID and 64-bit span ID to Datadog 64-bit integer strings."""
    try:
        dd_trace_id = str(int(trace_id_hex[-16:], 16)) if trace_id_hex else "0"
    except Exception:
        dd_trace_id = "0"
    try:
        dd_span_id = str(int(span_id_hex[-16:], 16)) if span_id_hex else "0"
    except Exception:
        dd_span_id = "0"
    return dd_trace_id, dd_span_id


def generate_trace_ids():
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    return trace_id, span_id


class DatadogLogger:
    """Datadog Structured Logger emitting to stdout & asynchronous OTLP bridge."""
    _stdout_lock = threading.Lock()

    @staticmethod
    def log(level: str, message: str, trace_id: str = "", span_id: str = "", logger_name: str = "argus.app", **kwargs):
        now_s = time.time()
        now_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(now_s)) + f".{int((now_s % 1) * 1e6):06d}Z"
        time_nano = int(now_s * 1e9)

        dd_trace_id, dd_span_id = trace_id_to_dd_ids(trace_id, span_id)
        status = level.lower()

        log_record = {
            "timestamp": now_iso,
            "status": status,
            "level": level.upper(),
            "service": SERVICE_NAME,
            "env": ENV,
            "version": VERSION,
            "ddsource": "python",
            "ddtags": f"env:{ENV},version:{VERSION},datacenter:{DATACENTER},role:{SERVICE_ROLE}",
            "trace_id": trace_id,
            "span_id": span_id,
            "dd.trace_id": dd_trace_id,
            "dd.span_id": dd_span_id,
            "logger.name": logger_name,
            "message": message,
            "k8s.pod.name": POD_NAME,
            "k8s.node.name": NODE_NAME,
            "k8s.namespace.name": NAMESPACE,
        }

        # Merge additional Datadog attributes
        for k, v in kwargs.items():
            if v is not None:
                log_record[k] = v

        # 1. Print structured JSON to stdout for Datadog / Docker / K8s log forwarders
        json_output = json.dumps(log_record)
        with DatadogLogger._stdout_lock:
            sys.stdout.write(json_output + "\n")
            sys.stdout.flush()

        # 2. Async forward to OTel Collector gateway for ClickHouse default.otel_logs
        severity_map = {"debug": 5, "info": 9, "warn": 13, "error": 17, "fatal": 21}
        sev_num = severity_map.get(status, 9)

        otlp_attrs = []
        for k, v in kwargs.items():
            if isinstance(v, (int, float)):
                otlp_attrs.append({"key": k, "value": {"doubleValue": float(v)}})
            elif isinstance(v, bool):
                otlp_attrs.append({"key": k, "value": {"boolValue": v}})
            else:
                otlp_attrs.append({"key": k, "value": {"stringValue": str(v)}})

        # Standard tags
        otlp_attrs.append({"key": "dd.trace_id", "value": {"stringValue": dd_trace_id}})
        otlp_attrs.append({"key": "dd.span_id", "value": {"stringValue": dd_span_id}})
        otlp_attrs.append({"key": "logger.name", "value": {"stringValue": logger_name}})

        otlp_log = {
            "timeUnixNano": str(time_nano),
            "observedTimeUnixNano": str(time_nano),
            "severityNumber": sev_num,
            "severityText": level.upper(),
            "body": {"stringValue": message},
            "attributes": otlp_attrs,
        }
        if trace_id:
            otlp_log["traceId"] = trace_id
        if span_id:
            otlp_log["spanId"] = span_id

        AsyncOTLPEmitter.queue_log(otlp_log)


class AsyncOTLPEmitter:
    """Asynchronous background batcher for traces and logs to Argus OTel Collector."""
    _log_queue = []
    _span_queue = []
    _lock = threading.Lock()
    _running = False

    @classmethod
    def start(cls):
        if not cls._running:
            cls._running = True
            t = threading.Thread(target=cls._worker, daemon=True)
            t.start()

    @classmethod
    def queue_log(cls, log_record):
        with cls._lock:
            cls._log_queue.append(log_record)
            if len(cls._log_queue) > 200:
                cls._log_queue.pop(0)

    @classmethod
    def queue_span(cls, span_record):
        with cls._lock:
            cls._span_queue.append(span_record)
            if len(cls._span_queue) > 200:
                cls._span_queue.pop(0)

    @classmethod
    def _worker(cls):
        while cls._running:
            time.sleep(0.5)
            logs_to_send = []
            spans_to_send = []
            with cls._lock:
                if cls._log_queue:
                    logs_to_send = cls._log_queue[:]
                    cls._log_queue.clear()
                if cls._span_queue:
                    spans_to_send = cls._span_queue[:]
                    cls._span_queue.clear()

            if logs_to_send:
                cls._send_logs(logs_to_send)
            if spans_to_send:
                cls._send_spans(spans_to_send)

    @classmethod
    def _send_logs(cls, logs):
        payload = {
            "resourceLogs": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
                            {"key": "service.version", "value": {"stringValue": VERSION}},
                            {"key": "deployment.environment", "value": {"stringValue": ENV}},
                            {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
                            {"key": "k8s.pod.name", "value": {"stringValue": POD_NAME}},
                            {"key": "k8s.node.name", "value": {"stringValue": NODE_NAME}},
                            {"key": "service.debug", "value": {"stringValue": "true"}},
                        ]
                    },
                    "scopeLogs": [
                        {
                            "scope": {"name": f"datadog.{SERVICE_NAME}", "version": VERSION},
                            "logRecords": logs,
                        }
                    ],
                }
            ]
        }
        try:
            cls._post("v1/logs", payload)
        except Exception:
            pass

    @classmethod
    def _send_spans(cls, spans):
        payload = {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
                            {"key": "service.version", "value": {"stringValue": VERSION}},
                            {"key": "deployment.environment", "value": {"stringValue": ENV}},
                            {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
                            {"key": "k8s.pod.name", "value": {"stringValue": POD_NAME}},
                            {"key": "k8s.node.name", "value": {"stringValue": NODE_NAME}},
                        ]
                    },
                    "scopeSpans": [
                        {
                            "scope": {"name": f"datadog.{SERVICE_NAME}", "version": VERSION},
                            "spans": spans,
                        }
                    ],
                }
            ]
        }
        try:
            cls._post("v1/traces", payload)
        except Exception:
            pass

    @classmethod
    def _post(cls, path, payload):
        url = f"{OTEL_GATEWAY_URL}/{path}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3) as resp:
            pass


def emit_span(trace_id, span_id, parent_span_id, name, start_ns, end_ns, status_code=200, kind=1, attrs=None):
    otel_status = {"code": 1} if status_code < 500 else {"code": 2, "message": f"HTTP {status_code}"}
    span_attrs = []
    if attrs:
        for k, v in attrs.items():
            if isinstance(v, (int, float)):
                span_attrs.append({"key": k, "value": {"doubleValue": float(v)}})
            elif isinstance(v, bool):
                span_attrs.append({"key": k, "value": {"boolValue": v}})
            else:
                span_attrs.append({"key": k, "value": {"stringValue": str(v)}})

    span_record = {
        "traceId": trace_id,
        "spanId": span_id,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(end_ns),
        "attributes": span_attrs,
        "status": otel_status,
    }
    if parent_span_id:
        span_record["parentSpanId"] = parent_span_id
    AsyncOTLPEmitter.queue_span(span_record)


def call_downstream(target_service: str, path: str, method: str = "GET", data_dict: dict = None, trace_id: str = "", parent_span_id: str = ""):
    """Dispatches a downstream HTTP call while propagating traceparent and logging every step."""
    base_url = DOWNSTREAM_MAP.get(target_service)
    if not base_url:
        raise ValueError(f"Unknown downstream service target: {target_service}")

    target_url = f"{base_url}{path}"
    client_span_id = uuid.uuid4().hex[:16]
    traceparent_header = f"00-{trace_id}-{client_span_id}-01" if trace_id else ""

    headers = {
        "Content-Type": "application/json",
        "User-Agent": f"ArgusDatadogClient/{SERVICE_NAME}",
        "x-datadog-trace-id": str(int(trace_id[-16:], 16)) if trace_id else "0",
        "x-datadog-parent-id": str(int(client_span_id, 16)),
    }
    if traceparent_header:
        headers["traceparent"] = traceparent_header

    # Step: Log downstream call dispatch
    DatadogLogger.log(
        "INFO",
        f"Downstream RPC call dispatched to {target_service}: {method} {path}",
        trace_id=trace_id,
        span_id=client_span_id,
        logger_name="argus.rpc.client",
        **{
            "rpc.system": "http",
            "rpc.service": target_service,
            "rpc.method": method,
            "rpc.url": target_url,
            "rpc.traceparent": traceparent_header,
        }
    )

    start_ns = int(time.time() * 1e9)
    start_t = time.time()
    body_bytes = json.dumps(data_dict).encode("utf-8") if data_dict is not None else None

    req = urllib.request.Request(target_url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_bytes = resp.read()
            duration_ms = round((time.time() - start_t) * 1000.0, 2)
            end_ns = int(time.time() * 1e9)
            resp_data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}

            DatadogLogger.log(
                "INFO",
                f"Downstream RPC call returned HTTP {resp.status} from {target_service} in {duration_ms}ms",
                trace_id=trace_id,
                span_id=client_span_id,
                logger_name="argus.rpc.client",
                **{
                    "rpc.service": target_service,
                    "rpc.status_code": resp.status,
                    "rpc.duration_ms": duration_ms,
                    "rpc.bytes_received": len(resp_bytes),
                }
            )

            emit_span(
                trace_id=trace_id,
                span_id=client_span_id,
                parent_span_id=parent_span_id,
                name=f"HTTP {method} {target_service}{path}",
                start_ns=start_ns,
                end_ns=end_ns,
                status_code=resp.status,
                kind=3,  # SPAN_KIND_CLIENT
                attrs={"http.url": target_url, "http.method": method, "http.status_code": resp.status}
            )
            return resp_data

    except urllib.error.HTTPError as e:
        duration_ms = round((time.time() - start_t) * 1000.0, 2)
        end_ns = int(time.time() * 1e9)
        err_msg = e.read().decode("utf-8", errors="replace")
        e.downstream_body = err_msg
        DatadogLogger.log(
            "ERROR",
            f"Downstream RPC call to {target_service} failed with HTTP {e.code}: {err_msg}",
            trace_id=trace_id,
            span_id=client_span_id,
            logger_name="argus.rpc.client",
            **{
                "rpc.service": target_service,
                "rpc.status_code": e.code,
                "rpc.duration_ms": duration_ms,
                "error.kind": "DownstreamHTTPError",
                "error.message": err_msg,
            }
        )
        emit_span(
            trace_id=trace_id,
            span_id=client_span_id,
            parent_span_id=parent_span_id,
            name=f"HTTP {method} {target_service}{path}",
            start_ns=start_ns,
            end_ns=end_ns,
            status_code=e.code,
            kind=3,
            attrs={"http.url": target_url, "http.method": method, "http.status_code": e.code, "error": True}
        )
        raise
    except Exception as e:
        duration_ms = round((time.time() - start_t) * 1000.0, 2)
        end_ns = int(time.time() * 1e9)
        DatadogLogger.log(
            "ERROR",
            f"Downstream RPC call to {target_service} raised network exception: {str(e)}",
            trace_id=trace_id,
            span_id=client_span_id,
            logger_name="argus.rpc.client",
            **{
                "rpc.service": target_service,
                "error.kind": type(e).__name__,
                "error.message": str(e),
                "error.stack": traceback.format_exc(),
            }
        )
        raise


class DatadogRequestHandler(BaseHTTPRequestHandler):
    """Exhaustive Datadog HTTP Request Handler logging every step."""

    def log_message(self, format, *args):
        # Suppress BaseHTTPRequestHandler standard stderr output to keep stdout purely JSON
        pass

    def _safe_write(self, payload: bytes) -> bool:
        """Write response bytes to client socket, dropping BrokenPipeError/ConnectionResetError quietly."""
        try:
            self.wfile.write(payload)
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False

    def _safe_send_response(self, status_code: int, headers: dict, payload: bytes) -> bool:
        """Send status, headers, and payload while quietly dropping early client disconnects."""
        try:
            self.send_response(status_code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError):
            return False
        return self._safe_write(payload)

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

    def _extract_traceparent(self):
        tp = self.headers.get("traceparent")
        if tp:
            parts = tp.split("-")
            if len(parts) == 4 and len(parts[1]) == 32 and len(parts[2]) == 16:
                return parts[1], parts[2]
        # Fallback to Datadog headers
        dd_trace = self.headers.get("x-datadog-trace-id")
        dd_parent = self.headers.get("x-datadog-parent-id")
        if dd_trace and dd_parent:
            try:
                t_hex = f"{int(dd_trace):032x}"
                s_hex = f"{int(dd_parent):016x}"
                return t_hex, s_hex
            except Exception:
                pass
        return generate_trace_ids()

    def do_GET(self):
        self._handle_request("GET")

    def do_POST(self):
        self._handle_request("POST")

    def _handle_request(self, method: str):
        parsed = urlparse(self.path)
        route = parsed.path
        query_params = parse_qs(parsed.query)
        start_t = time.time()
        start_ns = int(start_t * 1e9)
        client_ip = self.client_address[0] if self.client_address else "127.0.0.1"

        # 1. Healthcheck endpoint
        if route in ("/healthz", "/health"):
            self._safe_send_response(
                200,
                {"Content-Type": "application/json"},
                json.dumps({"status": "HEALTHY", "service": SERVICE_NAME, "role": SERVICE_ROLE, "version": VERSION}).encode("utf-8"),
            )
            return

        # 2. Prometheus /metrics endpoint
        if route == "/metrics":
            self._serve_metrics()
            return

        # Extract or generate Trace / Span
        trace_id, parent_span_id = self._extract_traceparent()
        server_span_id = uuid.uuid4().hex[:16]

        # Step 1: Ingress Log
        DatadogLogger.log(
            "INFO",
            f"HTTP request received: {method} {self.path}",
            trace_id=trace_id,
            span_id=server_span_id,
            logger_name="argus.http.ingress",
            **{
                "http.method": method,
                "http.url": self.path,
                "http.route": route,
                "http.user_agent": self.headers.get("User-Agent", "unknown"),
                "network.client.ip": client_ip,
                "http.request_id": self.headers.get("X-Request-ID", uuid.uuid4().hex[:8]),
            }
        )

        # Read body if present
        body_data = {}
        try:
            content_length = max(0, int(self.headers.get("Content-Length", 0) or 0))
        except ValueError:
            body_err = json.dumps({"error": "BadRequest", "message": "invalid Content-Length"}).encode("utf-8")
            self._safe_send_response(400, {"Content-Type": "application/json"}, body_err)
            return
        if content_length > 0:
            try:
                body_raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
            except (BrokenPipeError, ConnectionResetError):
                return
            try:
                body_data = json.loads(body_raw)
            except json.JSONDecodeError:
                body_err = json.dumps({"error": "BadRequest", "message": "malformed JSON"}).encode("utf-8")
                self._safe_send_response(400, {"Content-Type": "application/json"}, body_err)
                return
            if not isinstance(body_data, dict):
                body_err = json.dumps({"error": "BadRequest", "message": "JSON body must be an object"}).encode("utf-8")
                self._safe_send_response(400, {"Content-Type": "application/json"}, body_err)
                return
            DatadogLogger.log(
                "DEBUG",
                f"Parsed HTTP payload: {len(body_raw)} bytes",
                trace_id=trace_id,
                span_id=server_span_id,
                logger_name="argus.http.body",
                **{"http.payload_size_bytes": len(body_raw)}
            )

        # Trigger error check
        trigger_error = query_params.get("trigger_error", [None])[0] or body_data.get("trigger_error")

        try:
            # Dispatch to Role Business Logic
            response_data = self._dispatch_role_logic(route, method, query_params, body_data, trace_id, server_span_id, trigger_error)
            status_code = 200

            resp_bytes = json.dumps(response_data).encode("utf-8")
            self._safe_send_response(
                status_code,
                {
                    "Content-Type": "application/json",
                    "x-trace-id": trace_id,
                    "x-span-id": server_span_id,
                },
                resp_bytes,
            )

            duration_ms = round((time.time() - start_t) * 1000.0, 2)
            end_ns = int(time.time() * 1e9)

            # Step: Ingress Completion Log
            DatadogLogger.log(
                "INFO",
                f"HTTP request completed: {method} {route} -> 200 OK ({duration_ms}ms)",
                trace_id=trace_id,
                span_id=server_span_id,
                logger_name="argus.http.egress",
                **{
                    "http.status_code": status_code,
                    "duration_ms": duration_ms,
                    "http.bytes_sent": len(resp_bytes),
                }
            )

            record_metric_request(method, route, status_code, time.time() - start_t)
            emit_span(
                trace_id=trace_id,
                span_id=server_span_id,
                parent_span_id=parent_span_id,
                name=f"{SERVICE_NAME} {method} {route}",
                start_ns=start_ns,
                end_ns=end_ns,
                status_code=status_code,
                kind=1,
                attrs={"http.route": route, "http.method": method, "http.status_code": 200}
            )

        except Exception as exc:
            duration_ms = round((time.time() - start_t) * 1000.0, 2)
            end_ns = int(time.time() * 1e9)
            error_kind = type(exc).__name__
            error_msg = str(exc)
            status_code = 500
            if isinstance(exc, urllib.error.HTTPError):
                status_code = exc.code
                downstream_body = getattr(exc, "downstream_body", "")
                if downstream_body:
                    try:
                        parsed_err = json.loads(downstream_body)
                        if isinstance(parsed_err, dict):
                            error_kind = parsed_err.get("error") or error_kind
                            error_msg = parsed_err.get("message") or error_msg
                    except Exception:
                        pass
            elif "Declined" in error_kind or "Payment" in error_kind:
                status_code = 402
            elif "Exhausted" in error_kind or "Inventory" in error_kind:
                status_code = 409
            elif "Token" in error_kind or "Auth" in error_kind:
                status_code = 401
            elif "NotFound" in error_kind:
                status_code = 404

            # Datadog Error Log with Full Stack Trace
            DatadogLogger.log(
                "ERROR",
                f"Request failed with {error_kind}: {error_msg}",
                trace_id=trace_id,
                span_id=server_span_id,
                logger_name="argus.error",
                **{
                    "http.status_code": status_code,
                    "duration_ms": duration_ms,
                    "error.kind": error_kind,
                    "error.message": error_msg,
                    "error.stack": traceback.format_exc(),
                }
            )

            record_metric_request(method, route, status_code, time.time() - start_t)
            record_metric_error(error_kind)

            emit_span(
                trace_id=trace_id,
                span_id=server_span_id,
                parent_span_id=parent_span_id,
                name=f"{SERVICE_NAME} {method} {route}",
                start_ns=start_ns,
                end_ns=end_ns,
                status_code=status_code,
                kind=1,
                attrs={"http.route": route, "http.method": method, "http.status_code": status_code, "error": True}
            )

            err_resp = json.dumps({"error": error_kind, "message": error_msg, "trace_id": trace_id}).encode("utf-8")
            self._safe_send_response(
                status_code,
                {
                    "Content-Type": "application/json",
                    "x-trace-id": trace_id,
                },
                err_resp,
            )

    def _serve_metrics(self):
        lines = [
            f"# HELP http_requests_total Total number of HTTP requests processed by {SERVICE_NAME}",
            f"# TYPE http_requests_total counter",
        ]
        with METRICS_LOCK:
            for (m, r, s), count in HTTP_REQUESTS_TOTAL.items():
                lines.append(f'http_requests_total{{service="{SERVICE_NAME}",method="{m}",route="{r}",status="{s}"}} {count}')

            lines.append(f"# HELP http_request_duration_seconds Total latency of requests processed")
            lines.append(f"# TYPE http_request_duration_seconds summary")
            for r, s in HTTP_DURATION_SUM.items():
                cnt = HTTP_DURATION_COUNT.get(r, 1)
                lines.append(f'http_request_duration_seconds_sum{{service="{SERVICE_NAME}",route="{r}"}} {round(s, 4)}')
                lines.append(f'http_request_duration_seconds_count{{service="{SERVICE_NAME}",route="{r}"}} {cnt}')

            lines.append(f"# HELP db_queries_total Total DB queries executed by {SERVICE_NAME}")
            lines.append(f"# TYPE db_queries_total counter")
            lines.append(f'db_queries_total{{service="{SERVICE_NAME}"}} {DB_QUERIES_TOTAL}')

            lines.append(f"# HELP errors_total Total errors encountered by {SERVICE_NAME}")
            lines.append(f"# TYPE errors_total counter")
            for ek, ec in ERRORS_TOTAL.items():
                lines.append(f'errors_total{{service="{SERVICE_NAME}",error_type="{ek}"}} {ec}')

        out = "\n".join(lines) + "\n"
        self._safe_send_response(
            200,
            {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"},
            out.encode("utf-8"),
        )

    def _dispatch_role_logic(self, route: str, method: str, qparams: dict, body: dict, trace_id: str, span_id: str, trigger_error: str):
        """Dispatches role-specific microservice logic with full step-by-step Datadog logging."""

        # -------------------------------------------------------------
        # ROLE 1: GATEWAY (argus-svc-gateway :8001)
        # -------------------------------------------------------------
        if SERVICE_ROLE == "gateway":
            if route == "/api/checkout":
                # Step: Verify Auth
                DatadogLogger.log("INFO", "Step 1/3: Calling Auth service to verify user credentials", trace_id=trace_id, span_id=span_id, logger_name="argus.gateway.auth")
                auth_resp = call_downstream("auth", "/auth/verify", method="POST", data_dict={"user_token": "usr_tok_9918", "trigger_error": trigger_error}, trace_id=trace_id, parent_span_id=span_id)

                # Step: Query Catalog
                DatadogLogger.log("INFO", "Step 2/3: Calling Catalog service to retrieve item pricing", trace_id=trace_id, span_id=span_id, logger_name="argus.gateway.catalog")
                catalog_resp = call_downstream("catalog", "/catalog/items", method="GET", trace_id=trace_id, parent_span_id=span_id)

                # Step: Create Order
                DatadogLogger.log("INFO", "Step 3/3: Calling Order service to execute distributed transaction", trace_id=trace_id, span_id=span_id, logger_name="argus.gateway.order")
                order_resp = call_downstream("order", "/orders/create", method="POST", data_dict={"user_id": auth_resp.get("user_id"), "items": catalog_resp.get("items", []), "trigger_error": trigger_error}, trace_id=trace_id, parent_span_id=span_id)

                return {
                    "status": "CHECKOUT_COMPLETED",
                    "order": order_resp,
                    "auth": auth_resp,
                    "gateway": SERVICE_NAME,
                    "trace_id": trace_id
                }

            elif route == "/api/search":
                catalog_resp = call_downstream("catalog", "/catalog/items", method="GET", trace_id=trace_id, parent_span_id=span_id)
                rec_resp = call_downstream("recommendation", "/recommendation/for-user?user_id=usr_9918", method="GET", trace_id=trace_id, parent_span_id=span_id)
                return {"items": catalog_resp.get("items"), "recommendations": rec_resp.get("recommendations")}

            raise RouteNotFoundError(f"unmatched route: {method} {route}")

        # -------------------------------------------------------------
        # ROLE 2: AUTH (argus-svc-auth :8002)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "auth":
            if trigger_error in ("auth", "auth_expired"):
                raise TokenExpiredException("Agency JWT certificate token expired at 2026-10-16T00:00:00Z")

            # Emulate DB user lookup
            DatadogLogger.log("INFO", "DB Query: SELECT id, username, roles, agency_id FROM users WHERE token = '***'", trace_id=trace_id, span_id=span_id, logger_name="argus.db", **{"db.system": "postgresql", "db.table": "users"})
            record_metric_db_query()
            time.sleep(0.005)
            DatadogLogger.log("INFO", "DB Query completed: 1 user record retrieved in 5.2ms", trace_id=trace_id, span_id=span_id, logger_name="argus.db", **{"db.duration_ms": 5.2, "db.rows": 1})

            return {"user_id": "usr_9918", "username": "sre_operator", "roles": ["ADMIN", "OPERATOR"], "agency": "DHS_CISA"}

        # -------------------------------------------------------------
        # ROLE 3: CATALOG (argus-svc-catalog :8003)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "catalog":
            # Emulate Cache Lookup
            DatadogLogger.log("INFO", "Cache lookup: key='catalog:featured_items' status=HIT", trace_id=trace_id, span_id=span_id, logger_name="argus.cache", **{"cache.system": "redis", "cache.key": "catalog:featured_items", "cache.hit": True})
            # Emulate DB Query
            DatadogLogger.log("INFO", "DB Query: SELECT sku, name, unit_price FROM products WHERE active = true LIMIT 5", trace_id=trace_id, span_id=span_id, logger_name="argus.db", **{"db.system": "postgresql", "db.table": "products"})
            record_metric_db_query()

            items = [
                {"sku": "SKU-PRO-01", "name": "Argus Sensor Unit A1", "price": 129.99, "qty": 1},
                {"sku": "SKU-PRO-02", "name": "Telemetry Gateway Module", "price": 49.50, "qty": 2},
            ]
            return {"items": items, "count": len(items)}

        # -------------------------------------------------------------
        # ROLE 4: ORDER (argus-svc-order :8004)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "order":
            order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            DatadogLogger.log("INFO", f"Order initialized: {order_id}", trace_id=trace_id, span_id=span_id, logger_name="argus.order", **{"order.id": order_id, "order.status": "INITIALIZED"})

            # Step 1: Call Inventory
            DatadogLogger.log("INFO", f"Order {order_id} -> Reserving inventory items", trace_id=trace_id, span_id=span_id, logger_name="argus.order.inventory")
            inv_resp = call_downstream("inventory", "/inventory/reserve", method="POST", data_dict={"order_id": order_id, "trigger_error": trigger_error}, trace_id=trace_id, parent_span_id=span_id)

            # Step 2: Call Payment
            DatadogLogger.log("INFO", f"Order {order_id} -> Executing payment charge", trace_id=trace_id, span_id=span_id, logger_name="argus.order.payment")
            pay_resp = call_downstream("payment", "/payment/charge", method="POST", data_dict={"order_id": order_id, "amount": 228.99, "trigger_error": trigger_error}, trace_id=trace_id, parent_span_id=span_id)

            # Step 3: Call Shipping
            DatadogLogger.log("INFO", f"Order {order_id} -> Dispatching shipping carrier", trace_id=trace_id, span_id=span_id, logger_name="argus.order.shipping")
            ship_resp = call_downstream("shipping", "/shipping/dispatch", method="POST", data_dict={"order_id": order_id, "destination": "US_GOV_FACILITY_WEST"}, trace_id=trace_id, parent_span_id=span_id)

            # Step 4: Call Notification
            DatadogLogger.log("INFO", f"Order {order_id} -> Emitting order notification event", trace_id=trace_id, span_id=span_id, logger_name="argus.order.notification")
            notif_resp = call_downstream("notification", "/notification/send", method="POST", data_dict={"order_id": order_id, "channel": "EMAIL"}, trace_id=trace_id, parent_span_id=span_id)

            # Step 5: Call Recommendation
            DatadogLogger.log("INFO", f"Order {order_id} -> Emitting telemetry to recommendation engine", trace_id=trace_id, span_id=span_id, logger_name="argus.order.recommendation")
            rec_resp = call_downstream("recommendation", "/recommendation/record-event", method="POST", data_dict={"order_id": order_id, "user_id": body.get("user_id")}, trace_id=trace_id, parent_span_id=span_id)

            # Emulate Order state commit in DB
            DatadogLogger.log("INFO", f"DB Query: INSERT INTO orders (id, status, total) VALUES ('{order_id}', 'CONFIRMED', 228.99)", trace_id=trace_id, span_id=span_id, logger_name="argus.db", **{"db.system": "postgresql", "db.table": "orders"})
            record_metric_db_query()

            return {
                "order_id": order_id,
                "status": "CONFIRMED",
                "inventory": inv_resp,
                "payment": pay_resp,
                "shipping": ship_resp,
                "notification": notif_resp,
            }

        # -------------------------------------------------------------
        # ROLE 5: INVENTORY (argus-svc-inventory :8005)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "inventory":
            if trigger_error in ("inventory", "inventory_exhausted"):
                raise StockExhaustedException("Critical stock depletion: SKU-PRO-01 quantity available is 0")

            DatadogLogger.log("INFO", "DB Query: UPDATE warehouse_stock SET reserved = reserved + 1 WHERE sku = 'SKU-PRO-01'", trace_id=trace_id, span_id=span_id, logger_name="argus.db", **{"db.system": "postgresql", "db.table": "warehouse_stock"})
            record_metric_db_query()
            return {"status": "RESERVED", "reservation_id": f"RES-{uuid.uuid4().hex[:6].upper()}"}

        # -------------------------------------------------------------
        # ROLE 6: PAYMENT (argus-svc-payment :8006)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "payment":
            if trigger_error in ("payment", "payment_declined"):
                raise PaymentGatewayDeclinedException("Card declined by bank: 402 Insufficient Funds on test account")

            # Emulate fraud check
            DatadogLogger.log("INFO", "Fraud evaluation: model=gov_risk_v2 score=0.012 result=PASSED", trace_id=trace_id, span_id=span_id, logger_name="argus.payment.fraud")

            # Call Billing to create invoice
            bill_resp = call_downstream("billing", "/billing/invoice", method="POST", data_dict={"amount": body.get("amount", 228.99), "order_id": body.get("order_id")}, trace_id=trace_id, parent_span_id=span_id)

            return {
                "payment_id": f"PAY-{uuid.uuid4().hex[:8].upper()}",
                "status": "CAPTURED",
                "billing": bill_resp
            }

        # -------------------------------------------------------------
        # ROLE 7: BILLING (argus-svc-billing :8007)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "billing":
            invoice_id = f"INV-{uuid.uuid4().hex[:6].upper()}"
            DatadogLogger.log("INFO", f"Tax calculation: subtotal=228.99 tax_rate=0.0825 tax=18.89 total=247.88", trace_id=trace_id, span_id=span_id, logger_name="argus.billing.tax")
            DatadogLogger.log("INFO", f"DB Query: INSERT INTO invoices (invoice_id, order_id, total) VALUES ('{invoice_id}', '{body.get('order_id')}', 247.88)", trace_id=trace_id, span_id=span_id, logger_name="argus.db", **{"db.system": "postgresql", "db.table": "invoices"})
            record_metric_db_query()
            return {"invoice_id": invoice_id, "subtotal": 228.99, "tax": 18.89, "total": 247.88}

        # -------------------------------------------------------------
        # ROLE 8: SHIPPING (argus-svc-shipping :8008)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "shipping":
            trk = f"TRK-{uuid.uuid4().hex[:10].upper()}"
            DatadogLogger.log("INFO", f"Carrier dispatch: carrier=FEDEX_PRIORITY tracking_number={trk}", trace_id=trace_id, span_id=span_id, logger_name="argus.shipping.carrier", **{"shipping.carrier": "FEDEX_PRIORITY", "shipping.tracking": trk})
            return {"tracking_number": trk, "carrier": "FEDEX_PRIORITY", "estimated_delivery": "2026-10-18T18:00:00Z"}

        # -------------------------------------------------------------
        # ROLE 9: NOTIFICATION (argus-svc-notification :8009)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "notification":
            DatadogLogger.log("INFO", "Template rendering: template=order_confirmation.html render_time_ms=1.4", trace_id=trace_id, span_id=span_id, logger_name="argus.notification.template")
            DatadogLogger.log("INFO", "SMTP dispatch: recipient=sre_operator@agency.gov status=QUEUED", trace_id=trace_id, span_id=span_id, logger_name="argus.notification.smtp")
            return {"status": "DISPATCHED", "channel": "EMAIL", "recipient": "sre_operator@agency.gov"}

        # -------------------------------------------------------------
        # ROLE 10: RECOMMENDATION (argus-svc-recommendation :8010)
        # -------------------------------------------------------------
        elif SERVICE_ROLE == "recommendation":
            if route == "/recommendation/record-event":
                DatadogLogger.log("INFO", "Vector index updated: user_id=usr_9918 dimension=128 latency_ms=4.1", trace_id=trace_id, span_id=span_id, logger_name="argus.ml.vectors")
                return {"status": "RECORDED"}
            else:
                return {
                    "recommendations": [
                        {"sku": "SKU-PRO-03", "name": "Air-Gap Guardrail Filter", "affinity": 0.94},
                        {"sku": "SKU-PRO-04", "name": "GovCloud Bedrock Sidecar", "affinity": 0.88},
                    ]
                }

        raise RouteNotFoundError(f"unmatched route: {method} {route}")


# Custom Exceptions for Datadog Error Simulation
class RouteNotFoundError(Exception):
    pass

class TokenExpiredException(Exception):
    pass

class StockExhaustedException(Exception):
    pass

class PaymentGatewayDeclinedException(Exception):
    pass


def main():
    sys.stdout.write(f"Starting {SERVICE_NAME} (role={SERVICE_ROLE}) on port {PORT} in {DATACENTER}...\n")
    sys.stdout.flush()

    # Start Async OTLP Emitter loop
    AsyncOTLPEmitter.start()

    server = ThreadingHTTPServer(("0.0.0.0", PORT), DatadogRequestHandler)
    server.daemon_threads = True
    DatadogLogger.log(
        "INFO",
        f"{SERVICE_NAME} daemon started successfully and listening on port {PORT}",
        logger_name="argus.lifecycle",
        **{"port": PORT, "datacenter": DATACENTER, "env": ENV, "version": VERSION}
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
        DatadogLogger.log("INFO", f"{SERVICE_NAME} stopped.", logger_name="argus.lifecycle")


if __name__ == "__main__":
    main()
