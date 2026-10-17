#!/usr/bin/env python3
"""
Argus Feature F017: Real User Monitoring (RUM) & DOM Session Replay Collector
Provides:
1. Authenticated ingestion endpoint (/v1/rum/ingest) with defense-in-depth PII redaction & XSS sanitization.
2. Air-gapped client tracker script (/v1/rum/tracker.js) with client-side masking.
3. Session listing and query API (/v1/rum/sessions).
4. Full session replay timeline API (/v1/rum/replay/<session_id>).
5. Visual DOM Replay Player (/v1/rum/player/<session_id>) with strict CSP & safe DOM construction.
6. Parameterized / JSONEachRow ClickHouse persistence (default.rum_sessions, default.rum_events).
7. Prometheus metrics exposition (/metrics) and health probe (/healthz).
"""

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import signal
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("PORT", "8082"))
CLICKHOUSE_HTTP = os.environ.get(
    "CLICKHOUSE_HTTP",
    "http://chi-argus-clickhouse-argus-cluster-0-0.argus-system.svc.cluster.local:8123"
).rstrip("/")
CLICKHOUSE_USER = os.environ.get("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.environ.get("CLICKHOUSE_PASSWORD", "").strip()
RUM_INGEST_TOKEN = os.environ.get("RUM_INGEST_TOKEN", "").strip()
JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "https://argus.dhs.gov,http://localhost:8080,http://localhost:8082,http://localhost:8088"
    ).split(",") if o.strip()
]

# Metrics counters
METRICS_LOCK = threading.Lock()
TOTAL_SESSIONS = 0
TOTAL_EVENTS_BY_TYPE = {}
TOTAL_PII_REDACTED = 0

# In-memory storage for high-speed replay access & fallback
STORAGE_LOCK = threading.Lock()
IN_MEMORY_SESSIONS = {}  # session_id -> metadata
IN_MEMORY_EVENTS = {}    # session_id -> list of events

# Regex patterns for server-side defense-in-depth PII redaction
RE_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
RE_CREDIT_CARD = re.compile(r'\b(?:\d{4}[ -]?){3}\d{4}\b')
RE_SSN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
RE_BEARER = re.compile(r'(?i)Bearer\s+[A-Za-z0-9._~+/-]+=*')
RE_SECRET_KV = re.compile(r'(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|card|cvv|ssn)\b\s*[:=]\s*["\']?([^"\'\s&,]+)["\']?')

# Regex patterns for HTML/script XSS neutralization at ingest (C4)
RE_SCRIPT_TAG = re.compile(r'(?is)<\s*script\b[^>]*>.*?<\s*/\s*script\s*>')
RE_DANGEROUS_TAGS = re.compile(r'(?is)<\s*/?\s*(?:script|iframe|object|embed|applet|meta|base|svg|math)\b[^>]*>')
RE_EVENT_HANDLER_ATTR = re.compile(r'(?i)\s+on[a-z0-9_]+\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+)')
RE_JS_URI = re.compile(r'(?i)(?:javascript|vbscript|data\s*:\s*text/html)\s*:')

def sanitize_html_fragment(raw_html: str) -> str:
    """Strips executable script tags, dangerous containers, inline event handlers, and javascript: URIs."""
    if not isinstance(raw_html, str):
        return ""
    cleaned = RE_SCRIPT_TAG.sub("", raw_html)
    cleaned = RE_DANGEROUS_TAGS.sub("", cleaned)
    cleaned = RE_EVENT_HANDLER_ATTR.sub("", cleaned)
    cleaned = RE_JS_URI.sub("blocked:", cleaned)
    return cleaned

def safe_json_for_script(obj) -> str:
    """Safely serializes data to JSON for embedding inside an HTML <script> block without </script> breakout (C4)."""
    raw = json.dumps(obj)
    return (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )

def escape_clickhouse_string(val: str) -> str:
    """Escapes backslashes, single quotes, and control characters for ClickHouse string literals (H1)."""
    if not isinstance(val, str):
        val = str(val)
    return (
        val.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\0", "")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )

def redact_string(val: str) -> tuple[str, int]:
    """Sanitizes PII in string values, returning (sanitized_val, redacted_count)."""
    if not isinstance(val, str):
        return val, 0
    redactions = 0
    def repl_email(m):
        nonlocal redactions; redactions += 1; return "[REDACTED_EMAIL]"
    def repl_card(m):
        nonlocal redactions; redactions += 1; return "[REDACTED_CARD]"
    def repl_ssn(m):
        nonlocal redactions; redactions += 1; return "[REDACTED_SSN]"
    def repl_bearer(m):
        nonlocal redactions; redactions += 1; return "Bearer [REDACTED_TOKEN]"
    def repl_kv(m):
        nonlocal redactions; redactions += 1; return f"{m.group(1)}=[REDACTED]"

    res = RE_EMAIL.sub(repl_email, val)
    res = RE_CREDIT_CARD.sub(repl_card, res)
    res = RE_SSN.sub(repl_ssn, res)
    res = RE_BEARER.sub(repl_bearer, res)
    res = RE_SECRET_KV.sub(repl_kv, res)
    res = sanitize_html_fragment(res)
    return res, redactions

def deep_redact(obj) -> tuple[any, int]:
    """Recursively redacts PII and sanitizes active script payloads throughout nested dicts, lists, and strings."""
    redacted_count = 0
    if isinstance(obj, dict):
        new_dict = {}
        is_sensitive_context = (
            str(obj.get("field", "")).lower() in ("password", "passwd", "secret", "cvv", "credit_card", "ssn", "token") or
            str(obj.get("targetId", "")).lower() in ("password", "passwd", "pwd", "credit_card", "creditcard", "ssn", "cvv") or
            obj.get("isMasked") is True
        )
        for k, v in obj.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in ("password", "passwd", "secret", "cvv", "credit_card", "creditcard", "ssn", "token")):
                new_dict[k] = "[REDACTED]"
                redacted_count += 1
            elif is_sensitive_context and k_lower in ("value", "raw", "raw_value", "input_value", "text"):
                new_dict[k] = "[REDACTED]"
                redacted_count += 1
            elif k_lower == "bodyhtml" and isinstance(v, str):
                sanitized_v, count = redact_string(v)
                new_dict[k] = sanitize_html_fragment(sanitized_v)
                redacted_count += count
            else:
                new_v, count = deep_redact(v)
                new_dict[k] = new_v
                redacted_count += count
        return new_dict, redacted_count
    elif isinstance(obj, list):
        new_list = []
        for item in obj:
            new_item, count = deep_redact(item)
            new_list.append(new_item)
            redacted_count += count
        return new_list, redacted_count
    elif isinstance(obj, str):
        return redact_string(obj)
    return obj, 0

def _b64url_decode(s: str) -> bytes:
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)

def verify_rum_auth(headers) -> bool:
    """
    Authenticates RUM ingestion and replay queries via X-RUM-Ingest-Token, Bearer token, or session JWT (C4).
    Fails closed when neither RUM_INGEST_TOKEN nor JWT_SECRET is configured.
    """
    expected_ingest_tok = os.environ.get("RUM_INGEST_TOKEN", RUM_INGEST_TOKEN).strip()
    jwt_secret = os.environ.get("JWT_SECRET", JWT_SECRET).strip()
    if not expected_ingest_tok and not jwt_secret:
        return False

    # 1. Check X-RUM-Ingest-Token header
    ingest_hdr = headers.get("X-RUM-Ingest-Token", "").strip()
    if ingest_hdr and expected_ingest_tok and hmac.compare_digest(ingest_hdr.encode("utf-8"), expected_ingest_tok.encode("utf-8")):
        return True

    # 2. Extract Bearer token or session cookie
    token = ""
    auth_hdr = headers.get("Authorization", "").strip()
    if auth_hdr.startswith("Bearer "):
        token = auth_hdr.split(" ", 1)[1].strip()
    else:
        cookie_hdr = headers.get("Cookie", "")
        for c in cookie_hdr.split(";"):
            c = c.strip()
            if c.startswith("argus_session_token="):
                token = c.split("=", 1)[1].strip()
                break

    if not token:
        return False

    if expected_ingest_tok and hmac.compare_digest(token.encode("utf-8"), expected_ingest_tok.encode("utf-8")):
        return True

    if jwt_secret:
        parts = token.split(".")
        if len(parts) == 3:
            try:
                h_b64, p_b64, s_b64 = parts
                header = json.loads(_b64url_decode(h_b64).decode("utf-8"))
                if isinstance(header, dict) and header.get("alg") == "HS256":
                    expected_sig = hmac.new(jwt_secret.encode("utf-8"), f"{h_b64}.{p_b64}".encode("utf-8"), hashlib.sha256).digest()
                    if hmac.compare_digest(expected_sig, _b64url_decode(s_b64)):
                        payload = json.loads(_b64url_decode(p_b64).decode("utf-8"))
                        exp = payload.get("exp", 0)
                        if isinstance(exp, (int, float)) and exp >= time.time():
                            return True
            except Exception:
                pass

    return False

def execute_clickhouse_query(sql: str, params: dict = None) -> bool:
    """Executes a query (optionally parameterized) against ClickHouse HTTP interface (H1/H3)."""
    ch_pass = os.environ.get("CLICKHOUSE_PASSWORD", CLICKHOUSE_PASSWORD).strip()
    query_qs = {"wait_end_of_query": "1"}
    if params:
        for k, v in params.items():
            query_qs[f"param_{k}"] = str(v)
    url = f"{CLICKHOUSE_HTTP}/?{urllib.parse.urlencode(query_qs)}"
    req = urllib.request.Request(url, data=sql.encode("utf-8"), method="POST")
    auth = f"{CLICKHOUSE_USER}:{ch_pass}"
    b64_auth = base64.b64encode(auth.encode()).decode()
    req.add_header("Authorization", f"Basic {b64_auth}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        sys.stderr.write(f"ClickHouse query error: {e}\n")
        return False

TRACKER_JS = """/**
 * Argus Real User Monitoring (RUM) & Session Replay Tracker v1.0.0
 * Air-gapped, zero-dependency client session recorder with privacy masking.
 */
(function(window) {
    'use strict';
    var RUM = {
        sessionId: null,
        userId: null,
        traceId: null,
        ingestToken: null,
        collectorUrl: '/v1/rum/ingest',
        eventsQueue: [],
        maxQueue: 50,
        flushInterval: 2000,
        timer: null,

        init: function(opts) {
            opts = opts || {};
            this.collectorUrl = opts.collectorUrl || this.collectorUrl;
            this.ingestToken = opts.ingestToken || '';
            this.userId = opts.userId || 'anonymous-' + Math.random().toString(36).substr(2, 6);
            this.sessionId = opts.sessionId || 'sess-' + Math.random().toString(36).substr(2, 9);
            this.traceId = opts.traceId || this.generateTraceId();

            this.captureInitialSnapshot();
            this.bindListeners();
            this.startTimer();
            console.log('[ArgusRUM] Initialized session:', this.sessionId, 'trace:', this.traceId);
        },

        generateTraceId: function() {
            var chars = '0123456789abcdef';
            var s = '';
            for (var i = 0; i < 32; i++) s += chars.charAt(Math.floor(Math.random() * chars.length));
            return s;
        },

        isElementMasked: function(el) {
            if (!el) return false;
            if (el.type === 'password' || el.type === 'hidden') return true;
            if (el.getAttribute('data-masked') === 'true' || el.classList.contains('masked')) return true;
            var name = (el.name || el.id || '').toLowerCase();
            return /card|cvv|ssn|pwd|password|secret|token/.test(name);
        },

        maskValue: function(el) {
            if (!el || !el.value) return '';
            if (this.isElementMasked(el)) return '***';
            return el.value;
        },

        captureInitialSnapshot: function() {
            var domSnapshot = {
                title: document.title,
                url: window.location.href,
                bodyHtml: document.body ? document.body.innerHTML : '',
                timestamp: new Date().toISOString()
            };
            this.recordEvent('dom_snapshot', {
                snapshot: domSnapshot,
                selector: 'document'
            });
        },

        recordEvent: function(type, details) {
            var evt = {
                eventId: 'evt-' + Math.random().toString(36).substr(2, 9),
                timestamp: new Date().toISOString(),
                type: type,
                targetTag: details.tag || '',
                targetId: details.id || '',
                targetClass: details.className || '',
                targetSelector: details.selector || '',
                maskedValue: details.maskedValue || '',
                payload: details
            };
            this.eventsQueue.push(evt);
            if (this.eventsQueue.length >= this.maxQueue) {
                this.flush();
            }
        },

        bindListeners: function() {
            var self = this;
            // Click listener
            document.addEventListener('click', function(e) {
                var el = e.target;
                if (!el) return;
                self.recordEvent('click', {
                    tag: el.tagName ? el.tagName.toLowerCase() : '',
                    id: el.id || '',
                    className: el.className || '',
                    selector: el.tagName ? el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') : '',
                    text: el.innerText ? el.innerText.substr(0, 50) : ''
                });
            }, true);

            // Input listener with strict client-side PII masking
            document.addEventListener('input', function(e) {
                var el = e.target;
                if (!el || !el.tagName || !/input|textarea|select/i.test(el.tagName)) return;
                var isMasked = self.isElementMasked(el);
                self.recordEvent('input', {
                    tag: el.tagName.toLowerCase(),
                    id: el.id || '',
                    className: el.className || '',
                    selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                    maskedValue: isMasked ? '***' : el.value,
                    isMasked: isMasked
                });
            }, true);

            // Console error listener
            window.addEventListener('error', function(e) {
                self.recordEvent('console_error', {
                    message: e.message || '',
                    filename: e.filename || '',
                    lineno: e.lineno || 0,
                    colno: e.colno || 0
                });
            });
        },

        flush: function() {
            if (this.eventsQueue.length === 0) return;
            var batch = this.eventsQueue.slice(0);
            this.eventsQueue = [];

            var payload = {
                sessionId: this.sessionId,
                userId: this.userId,
                traceId: this.traceId,
                pageUrl: window.location.pathname,
                userAgent: navigator.userAgent,
                events: batch
            };

            var dataStr = JSON.stringify(payload);
            var headers = { 'Content-Type': 'application/json' };
            if (this.ingestToken) {
                headers['X-RUM-Ingest-Token'] = this.ingestToken;
            }
            fetch(this.collectorUrl, {
                method: 'POST',
                headers: headers,
                body: dataStr,
                keepalive: true,
                credentials: 'same-origin'
            }).catch(function(err) {});
        },

        startTimer: function() {
            var self = this;
            this.timer = setInterval(function() {
                self.flush();
            }, this.flushInterval);
        }
    };

    window.ArgusRUM = RUM;
})(window);
"""

def generate_player_html(session_id: str, session: dict, events: list, csp_nonce: str = "") -> str:
    """Generates the interactive, responsive DOM Replay Player HTML page with XSS-safe JSON & DOM construction (C4)."""
    s_id = html.escape(str(session_id))
    user_id = html.escape(str(session.get("userId", "anonymous")))
    trace_id = html.escape(str(session.get("traceId", "none")))
    page_url = html.escape(str(session.get("pageUrl", "/")))
    duration_s = round(float(session.get("durationMs", 0)) / 1000.0, 2)
    ev_count = len(events)
    err_count = int(session.get("errorsCount", 0))

    # Safely encode JSON for <script> context so </script>, <!--, <, >, & are neutralized (C4)
    events_json = safe_json_for_script(events)
    nonce_attr = f' nonce="{html.escape(csp_nonce)}"' if csp_nonce else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Argus RUM Session Replay — {s_id}</title>
    <style{nonce_attr}>
        :root {{
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-accent: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-cyan: #06b6d4;
            --accent-emerald: #10b981;
            --accent-rose: #f43f5e;
            --accent-amber: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
        }}
        header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--bg-accent);
            padding: 12px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 700;
            font-size: 1.15rem;
            color: var(--accent-cyan);
        }}
        .badge {{
            font-size: 0.75rem;
            padding: 3px 8px;
            border-radius: 9999px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-active {{ background: rgba(16, 185, 129, 0.2); color: var(--accent-emerald); }}
        .badge-masked {{ background: rgba(244, 63, 94, 0.2); color: var(--accent-rose); }}
        .meta-group {{
            display: flex;
            gap: 20px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        .meta-group strong {{ color: var(--text-primary); }}
        .meta-trace a {{ color: var(--accent-cyan); text-decoration: none; }}
        .meta-trace a:hover {{ text-decoration: underline; }}
        
        main {{
            display: grid;
            grid-template-columns: 1fr 360px;
            flex: 1;
            overflow: hidden;
        }}
        .player-viewport {{
            display: flex;
            flex-direction: column;
            background: #000;
            position: relative;
        }}
        .viewport-frame {{
            flex: 1;
            padding: 24px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #111827;
        }}
        .screen-container {{
            width: 100%;
            max-width: 900px;
            height: 100%;
            background: #ffffff;
            color: #1f2937;
            border-radius: 8px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
            padding: 24px;
            overflow-y: auto;
            position: relative;
        }}
        .player-controls {{
            background: var(--bg-secondary);
            border-top: 1px solid var(--bg-accent);
            padding: 12px 24px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: var(--bg-accent);
            border-radius: 3px;
            position: relative;
            cursor: pointer;
        }}
        .progress-fill {{
            height: 100%;
            width: 0%;
            background: var(--accent-cyan);
            border-radius: 3px;
            transition: width 0.1s linear;
        }}
        .controls-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        .playback-btn {{
            background: var(--accent-cyan);
            color: #0f172a;
            border: none;
            padding: 6px 14px;
            border-radius: 4px;
            font-weight: 600;
            cursor: pointer;
        }}
        .playback-btn:hover {{ opacity: 0.9; }}
        .events-panel {{
            background: var(--bg-secondary);
            border-left: 1px solid var(--bg-accent);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        .panel-header {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--bg-accent);
            font-weight: 600;
            font-size: 0.9rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .events-list {{
            flex: 1;
            overflow-y: auto;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .event-card {{
            background: var(--bg-primary);
            border: 1px solid var(--bg-accent);
            border-radius: 6px;
            padding: 10px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: border-color 0.15s;
        }}
        .event-card:hover, .event-card.active {{
            border-color: var(--accent-cyan);
        }}
        .event-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 4px;
        }}
        .event-type {{
            font-weight: 700;
            color: var(--accent-cyan);
        }}
        .event-type.input {{ color: var(--accent-amber); }}
        .event-type.click {{ color: var(--accent-emerald); }}
        .event-type.console_error {{ color: var(--accent-rose); }}
        .event-masked {{
            display: inline-block;
            background: rgba(244, 63, 94, 0.2);
            color: var(--accent-rose);
            font-size: 0.7rem;
            padding: 1px 4px;
            border-radius: 3px;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <span>🛡️ Argus RUM Replay</span>
            <span class="badge badge-active">Session Active</span>
            <span class="badge badge-masked">PII Redacted</span>
        </div>
        <div class="meta-group">
            <div>Session: <strong>{s_id}</strong></div>
            <div>User: <strong>{user_id}</strong></div>
            <div>Page: <strong>{page_url}</strong></div>
            <div>Duration: <strong>{duration_s}s</strong></div>
            <div>Events: <strong>{ev_count}</strong></div>
            <div class="meta-trace">Trace: <a href="/api/v1/traces/{trace_id}"><strong>{trace_id[:12]}...</strong></a></div>
        </div>
    </header>

    <main>
        <div class="player-viewport">
            <div class="viewport-frame">
                <div class="screen-container" id="domScreen">
                    <h2 style="margin-bottom: 12px; color: #1e293b;">DOM State Replay Viewport</h2>
                    <p style="color: #64748b; font-size: 0.9rem;">Interactive snapshot of client-rendered DOM with masked form fields.</p>
                    <hr style="margin: 16px 0; border: none; border-top: 1px solid #e2e8f0;">
                    <div id="reconstructedDom">
                        <!-- Populated safely via DOM APIs -->
                    </div>
                </div>
            </div>

            <div class="player-controls">
                <div class="progress-bar" id="progressBar">
                    <div class="progress-fill" id="progressFill"></div>
                </div>
                <div class="controls-row">
                    <div style="display: flex; gap: 8px;">
                        <button class="playback-btn" id="playBtn">Play ▶</button>
                        <button class="playback-btn" style="background: var(--bg-accent); color: #fff;" id="stepBtn">Step ❯</button>
                    </div>
                    <div style="font-size: 0.85rem; color: var(--text-secondary);" id="timeDisplay">
                        0.00s / {duration_s}s
                    </div>
                </div>
            </div>
        </div>

        <div class="events-panel">
            <div class="panel-header">
                <span>Event Stream ({ev_count})</span>
                <span style="font-size: 0.75rem; color: var(--accent-rose);">{err_count} errors</span>
            </div>
            <div class="events-list" id="eventsList">
                <!-- Dynamically populated via textContent -->
            </div>
        </div>
    </main>

    <script{nonce_attr}>
        const events = {events_json};
        let currentIndex = 0;
        let isPlaying = false;
        let timer = null;

        const screen = document.getElementById('reconstructedDom');
        const list = document.getElementById('eventsList');
        const fill = document.getElementById('progressFill');
        const timeDisplay = document.getElementById('timeDisplay');
        const playBtn = document.getElementById('playBtn');

        const SAFE_TAGS = new Set(['DIV', 'SPAN', 'P', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'FORM', 'LABEL', 'INPUT', 'BUTTON', 'HR', 'UL', 'OL', 'LI', 'STRONG', 'EM', 'CODE']);
        const SAFE_ATTRS = new Set(['id', 'class', 'type', 'name', 'value', 'placeholder', 'alt', 'data-index', 'data-masked']);

        function sanitizeDomTree(htmlString) {{
            const parser = new DOMParser();
            const doc = parser.parseFromString(String(htmlString || ''), 'text/html');
            const fragment = document.createDocumentFragment();

            function cloneSafeNode(node) {{
                if (node.nodeType === Node.TEXT_NODE) {{
                    return document.createTextNode(node.textContent || '');
                }}
                if (node.nodeType !== Node.ELEMENT_NODE) {{
                    return null;
                }}
                const tagName = node.tagName.toUpperCase();
                if (!SAFE_TAGS.has(tagName)) {{
                    return null;
                }}
                const el = document.createElement(tagName.toLowerCase());
                for (const attr of Array.from(node.attributes)) {{
                    const name = attr.name.toLowerCase();
                    if (SAFE_ATTRS.has(name)) {{
                        el.setAttribute(name, attr.value);
                    }}
                }}
                for (const child of Array.from(node.childNodes)) {{
                    const safeChild = cloneSafeNode(child);
                    if (safeChild) {{
                        el.appendChild(safeChild);
                    }}
                }}
                return el;
            }}

            if (doc.body) {{
                for (const child of Array.from(doc.body.childNodes)) {{
                    const safeChild = cloneSafeNode(child);
                    if (safeChild) {{
                        fragment.appendChild(safeChild);
                    }}
                }}
            }}
            return fragment;
        }}

        function renderEventsList() {{
            list.replaceChildren();
            events.forEach((ev, i) => {{
                const card = document.createElement('div');
                card.className = 'event-card' + (i === currentIndex ? ' active' : '');
                const isMasked = Boolean(ev.maskedValue || (ev.payload && ev.payload.isMasked));

                const header = document.createElement('div');
                header.className = 'event-header';

                const typeSpan = document.createElement('span');
                const safeType = String(ev.type || 'unknown').replace(/[^a-zA-Z0-9_-]/g, '');
                typeSpan.className = 'event-type ' + safeType;
                typeSpan.textContent = String(ev.type || 'unknown');

                const timeSpan = document.createElement('span');
                timeSpan.style.color = 'var(--text-secondary)';
                const tsParts = String(ev.timestamp || '').split('T');
                timeSpan.textContent = tsParts.length > 1 ? tsParts[1].substr(0, 8) : String(ev.timestamp || '');

                header.appendChild(typeSpan);
                header.appendChild(timeSpan);

                const targetDiv = document.createElement('div');
                targetDiv.appendChild(document.createTextNode('Target: '));
                const targetCode = document.createElement('code');
                targetCode.textContent = String(ev.targetSelector || ev.targetTag || 'body');
                targetDiv.appendChild(targetCode);

                card.appendChild(header);
                card.appendChild(targetDiv);

                if (isMasked) {{
                    const maskedBadge = document.createElement('div');
                    maskedBadge.className = 'event-masked';
                    maskedBadge.textContent = '🛡️ PII Masked (***)';
                    card.appendChild(maskedBadge);
                }}

                card.onclick = () => jumpTo(i);
                list.appendChild(card);
            }});
        }}

        function applyEvent(ev) {{
            if (ev.type === 'dom_snapshot' && ev.payload && ev.payload.snapshot) {{
                const rawHtml = ev.payload.snapshot.bodyHtml;
                if (rawHtml) {{
                    screen.replaceChildren(sanitizeDomTree(rawHtml));
                }} else {{
                    const emptyP = document.createElement('p');
                    emptyP.style.color = '#64748b';
                    emptyP.textContent = '[Blank DOM Snapshot]';
                    screen.replaceChildren(emptyP);
                }}
            }} else if (ev.type === 'input') {{
                try {{
                    const target = screen.querySelector(ev.targetSelector);
                    if (target) {{
                        target.value = ev.maskedValue || '***';
                    }}
                }} catch (e) {{}}
            }} else if (ev.type === 'click') {{
                try {{
                    const target = screen.querySelector(ev.targetSelector);
                    if (target) {{
                        target.style.outline = '2px solid #06b6d4';
                        setTimeout(() => target.style.outline = '', 400);
                    }}
                }} catch (e) {{}}
            }}
        }}

        function step() {{
            if (currentIndex >= events.length) {{
                pause();
                return;
            }}
            applyEvent(events[currentIndex]);
            currentIndex++;
            updateUI();
        }}

        function updateUI() {{
            const pct = events.length > 0 ? (currentIndex / events.length) * 100 : 0;
            fill.style.width = pct + '%';
            timeDisplay.textContent = currentIndex + ' / ' + events.length + ' events';
            document.querySelectorAll('.event-card').forEach((c, idx) => {{
                c.classList.toggle('active', idx === currentIndex - 1);
            }});
        }}

        function play() {{
            isPlaying = true;
            playBtn.textContent = 'Pause ❚❚';
            timer = setInterval(() => {{
                if (currentIndex >= events.length) {{
                    pause();
                }} else {{
                    step();
                }}
            }}, 300);
        }}

        function pause() {{
            isPlaying = false;
            playBtn.textContent = 'Play ▶';
            if (timer) clearInterval(timer);
        }}

        function jumpTo(idx) {{
            pause();
            currentIndex = 0;
            screen.replaceChildren();
            for (let i = 0; i <= idx && i < events.length; i++) {{
                applyEvent(events[i]);
            }}
            currentIndex = idx + 1;
            updateUI();
        }}

        playBtn.onclick = () => {{
            if (isPlaying) pause(); else play();
        }};
        document.getElementById('stepBtn').onclick = () => {{
            pause();
            step();
        }};

        renderEventsList();
        if (events.length > 0) {{
            step();
        }}
    </script>
</body>
</html>
"""

class RUMRequestHandler(BaseHTTPRequestHandler):
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

    def _apply_cors_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        origin = self.headers.get("Origin", "")
        if origin and origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-RUM-Ingest-Token, traceparent")

    def send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._apply_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin", "")
        if origin and origin in ALLOWED_ORIGINS:
            self.send_response(204)
            self._apply_cors_headers()
            self.end_headers()
        else:
            self.send_response(403)
            self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Health probe
        if path == "/healthz":
            self.send_json(200, {"status": "ok", "service": "argus-rum-collector"})
            return

        # Prometheus metrics
        if path == "/metrics":
            with METRICS_LOCK:
                lines = [
                    "# HELP argus_rum_sessions_total Total RUM user sessions captured",
                    "# TYPE argus_rum_sessions_total counter",
                    f"argus_rum_sessions_total {TOTAL_SESSIONS}",
                    "# HELP argus_rum_pii_redacted_total Total sensitive PII values redacted at ingest",
                    "# TYPE argus_rum_pii_redacted_total counter",
                    f"argus_rum_pii_redacted_total {TOTAL_PII_REDACTED}",
                    "# HELP argus_rum_events_total Total RUM events captured by event type",
                    "# TYPE argus_rum_events_total counter"
                ]
                for etype, cnt in TOTAL_EVENTS_BY_TYPE.items():
                    safe_etype = re.sub(r'[^a-zA-Z0-9_-]', '_', str(etype))
                    lines.append(f'argus_rum_events_total{{event_type="{safe_etype}"}} {cnt}')
                lines.append("")
                body = "\n".join(lines).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        # Client-side tracker script
        if path == "/v1/rum/tracker.js":
            body = TRACKER_JS.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._apply_cors_headers()
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(body)
            return

        # List sessions (requires auth)
        if path in ("/v1/rum/sessions", "/v1/rum/sessions/"):
            if not verify_rum_auth(self.headers):
                self.send_json(401, {"error": "unauthorized", "message": "Authentication required to list RUM sessions"})
                return
            trace_id_filter = query.get("trace_id", [None])[0]
            with STORAGE_LOCK:
                sessions_list = []
                for s_id, s_meta in IN_MEMORY_SESSIONS.items():
                    if trace_id_filter and s_meta.get("traceId") != trace_id_filter:
                        continue
                    sessions_list.append(s_meta)
            self.send_json(200, {"sessions": sessions_list, "count": len(sessions_list)})
            return

        # Full session replay JSON (requires auth)
        if path.startswith("/v1/rum/replay/"):
            if not verify_rum_auth(self.headers):
                self.send_json(401, {"error": "unauthorized", "message": "Authentication required to access session replay"})
                return
            session_id = path.replace("/v1/rum/replay/", "").strip("/")
            with STORAGE_LOCK:
                s_meta = IN_MEMORY_SESSIONS.get(session_id)
                events = IN_MEMORY_EVENTS.get(session_id, [])
            if not s_meta:
                self.send_json(404, {"error": "session not found", "sessionId": session_id})
                return
            self.send_json(200, {
                "sessionId": session_id,
                "session": s_meta,
                "events": events,
                "eventCount": len(events)
            })
            return

        # Visual DOM Replay Player HTML (requires auth + strict CSP — C4)
        if path.startswith("/v1/rum/player/"):
            if not verify_rum_auth(self.headers):
                self.send_json(401, {"error": "unauthorized", "message": "Authentication required to open replay player"})
                return
            session_id = path.replace("/v1/rum/player/", "").strip("/")
            with STORAGE_LOCK:
                s_meta = IN_MEMORY_SESSIONS.get(session_id, {
                    "sessionId": session_id,
                    "userId": "unknown",
                    "traceId": "none",
                    "pageUrl": "/",
                    "durationMs": 0,
                    "errorsCount": 0
                })
                events = IN_MEMORY_EVENTS.get(session_id, [])
            csp_nonce = secrets.token_hex(16)
            html_content = generate_player_html(session_id, s_meta, events, csp_nonce=csp_nonce).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_content)))
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; script-src 'nonce-{csp_nonce}'; style-src 'nonce-{csp_nonce}' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
            self._apply_cors_headers()
            self.end_headers()
            self.wfile.write(html_content)
            return

        # Sample interactive frontend demonstrating RUM and PII masking
        if path in ("/checkout", "/v1/rum/sample"):
            csp_nonce = secrets.token_hex(16)
            sample_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Argus Store — Secure Checkout</title>
    <style nonce="{csp_nonce}">
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; }}
        .checkout-container {{ max-width: 600px; margin: 0 auto; background: #1e293b; padding: 28px; border-radius: 8px; border: 1px solid #334155; }}
        h1 {{ font-size: 1.5rem; margin-bottom: 8px; color: #06b6d4; }}
        p.subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-bottom: 24px; }}
        .form-group {{ margin-bottom: 16px; }}
        label {{ display: block; margin-bottom: 6px; font-size: 0.85rem; font-weight: 600; color: #cbd5e1; }}
        .masked-badge {{ font-size: 0.7rem; background: rgba(244, 63, 94, 0.2); color: #f43f5e; padding: 2px 6px; border-radius: 4px; margin-left: 6px; }}
        input {{ width: 100%; padding: 10px 12px; background: #0f172a; border: 1px solid #334155; border-radius: 4px; color: #fff; font-size: 0.95rem; box-sizing: border-box; }}
        input:focus {{ border-color: #06b6d4; outline: none; }}
        button {{ width: 100%; background: #06b6d4; color: #0f172a; border: none; padding: 12px; border-radius: 4px; font-weight: 700; font-size: 1rem; cursor: pointer; margin-top: 8px; }}
        button:hover {{ opacity: 0.9; }}
        .feedback {{ margin-top: 16px; padding: 12px; border-radius: 4px; display: none; font-size: 0.9rem; }}
        .feedback.success {{ background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }}
    </style>
    <script nonce="{csp_nonce}" src="/v1/rum/tracker.js"></script>
    <script nonce="{csp_nonce}">
        document.addEventListener('DOMContentLoaded', function() {{
            if (window.ArgusRUM) {{
                window.ArgusRUM.init({{
                    collectorUrl: '/v1/rum/ingest',
                    userId: 'customer-jane-doe',
                    sessionId: 'sess-sample-demo'
                }});
            }}
        }});
        function handleCheckout(e) {{
            e.preventDefault();
            if (window.ArgusRUM) {{
                window.ArgusRUM.recordEvent('click', {{ tag: 'button', id: 'submitBtn', text: 'Complete Purchase' }});
                window.ArgusRUM.flush();
            }}
            const fb = document.getElementById('feedbackMsg');
            fb.style.display = 'block';
            fb.className = 'feedback success';
            fb.textContent = 'Order submitted successfully! RUM telemetry beacon flushed.';
        }}
        document.addEventListener('DOMContentLoaded', function() {{
            const form = document.getElementById('checkoutForm');
            if (form) form.addEventListener('submit', handleCheckout);
        }});
    </script>
</head>
<body>
    <div class="checkout-container">
        <h1>Argus Store — Secure Checkout</h1>
        <p class="subtitle">Demonstrating Client-Side and Server-Side PII Masking during DOM Session Recording</p>
        <form id="checkoutForm" autocomplete="off">
            <div class="form-group">
                <label for="fullName">Full Name (Public Field)</label>
                <input type="text" id="fullName" name="fullName" value="Jane Doe" required>
            </div>
            <div class="form-group">
                <label for="email">Email Address <span class="masked-badge">PII Sanitized</span></label>
                <input type="email" id="email" name="email" value="jane.doe@argus.internal" required>
            </div>
            <div class="form-group">
                <label for="password">Account Password <span class="masked-badge">Masked (***)</span></label>
                <input type="password" id="password" name="password" placeholder="••••••••••••" required>
            </div>
            <div class="form-group">
                <label for="creditCard">Credit Card Number <span class="masked-badge">Masked (***)</span></label>
                <input type="text" id="creditCard" name="creditCard" data-masked="true" placeholder="••••-••••-••••-••••" required>
            </div>
            <div class="form-group">
                <label for="deliveryNotes">Delivery Instructions (Public Field)</label>
                <input type="text" id="deliveryNotes" name="deliveryNotes" value="Leave package at the front desk">
            </div>
            <button type="submit" id="submitBtn">Complete Purchase</button>
            <div id="feedbackMsg" class="feedback"></div>
        </form>
    </div>
</body>
</html>""".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(sample_html)))
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; script-src 'self' 'nonce-{csp_nonce}'; style-src 'nonce-{csp_nonce}' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
            )
            self._apply_cors_headers()
            self.end_headers()
            self.wfile.write(sample_html)
            return

        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/v1/rum/ingest", "/v1/rum/ingest/"):
            # Require authentication on ingest (C4)
            if not verify_rum_auth(self.headers):
                self.send_json(401, {"error": "unauthorized", "message": "Valid RUM ingest token or Bearer JWT required"})
                return

            content_len = int(self.headers.get("Content-Length", 0))
            if content_len == 0:
                self.send_json(400, {"error": "empty payload"})
                return

            try:
                body_bytes = self.rfile.read(content_len)
                body_str = body_bytes.decode("utf-8")
                raw_payload = json.loads(body_str)
            except Exception as e:
                self.send_json(400, {"error": f"invalid json: {e}"})
                return

            if not isinstance(raw_payload, dict):
                self.send_json(400, {"error": "payload must be a JSON object"})
                return

            session_id = raw_payload.get("sessionId")
            if not session_id or not isinstance(session_id, str):
                self.send_json(400, {"error": "missing or invalid sessionId"})
                return

            # Apply server-side defense-in-depth PII sanitization & HTML/XSS stripping (C4)
            sanitized_payload, pii_redactions = deep_redact(raw_payload)

            user_id = str(sanitized_payload.get("userId", "anonymous"))
            user_email = str(sanitized_payload.get("userEmail", ""))
            trace_id = str(sanitized_payload.get("traceId", ""))
            page_url = str(sanitized_payload.get("pageUrl", "/"))
            user_agent = str(sanitized_payload.get("userAgent", self.headers.get("User-Agent", "")))
            client_ip = self.client_address[0] if self.client_address else "127.0.0.1"
            # Mask client IP (keep first 2 octets)
            ip_parts = client_ip.split(".")
            ip_masked = f"{ip_parts[0]}.{ip_parts[1]}.0.0" if len(ip_parts) == 4 else client_ip

            events = sanitized_payload.get("events", [])
            if not isinstance(events, list):
                events = []

            now_iso = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
            errors_in_batch = sum(1 for e in events if isinstance(e, dict) and e.get("type") == "console_error")

            # Store in memory
            with STORAGE_LOCK:
                if session_id not in IN_MEMORY_SESSIONS:
                    IN_MEMORY_SESSIONS[session_id] = {
                        "sessionId": session_id,
                        "userId": user_id,
                        "userEmail": user_email,
                        "traceId": trace_id,
                        "pageUrl": page_url,
                        "userAgent": user_agent,
                        "ipMasked": ip_masked,
                        "startTime": now_iso,
                        "endTime": now_iso,
                        "durationMs": 0,
                        "eventsCount": 0,
                        "errorsCount": 0,
                        "piiRedacted": 0
                    }
                    IN_MEMORY_EVENTS[session_id] = []
                    with METRICS_LOCK:
                        global TOTAL_SESSIONS
                        TOTAL_SESSIONS += 1

                s_meta = IN_MEMORY_SESSIONS[session_id]
                s_meta["endTime"] = now_iso
                s_meta["eventsCount"] += len(events)
                s_meta["errorsCount"] += errors_in_batch
                s_meta["piiRedacted"] += pii_redactions
                IN_MEMORY_EVENTS[session_id].extend(events)

            # Update metrics
            with METRICS_LOCK:
                global TOTAL_PII_REDACTED
                TOTAL_PII_REDACTED += pii_redactions
                for e in events:
                    if isinstance(e, dict):
                        etype = str(e.get("type", "unknown"))
                        TOTAL_EVENTS_BY_TYPE[etype] = TOTAL_EVENTS_BY_TYPE.get(etype, 0) + 1

            # Asynchronous ClickHouse ingestion using parameterized queries / JSONEachRow (H1)
            def persist_clickhouse():
                sql_session = """
                INSERT INTO default.rum_sessions (
                    session_id, user_id, user_email_masked, start_time, end_time,
                    duration_ms, events_count, errors_count, trace_id, user_agent,
                    page_url, ip_masked, metadata
                ) VALUES (
                    {s_id:String}, {u_id:String}, {u_email:String},
                    {start_ts:String}, {end_ts:String}, 1000, {ev_cnt:UInt32}, {err_cnt:UInt32},
                    {t_id:String}, {u_agent:String}, {p_url:String}, {ip_m:String},
                    map('collector', 'argus-rum-collector')
                )
                """
                execute_clickhouse_query(sql_session, params={
                    "s_id": session_id,
                    "u_id": user_id,
                    "u_email": user_email,
                    "start_ts": now_iso,
                    "end_ts": now_iso,
                    "ev_cnt": len(events),
                    "err_cnt": errors_in_batch,
                    "t_id": trace_id,
                    "u_agent": user_agent,
                    "p_url": page_url,
                    "ip_m": ip_masked,
                })

                # Batch insert events via JSONEachRow (completely immune to SQL string literal injection — H1)
                if events:
                    json_rows = []
                    for ev in events:
                        if not isinstance(ev, dict):
                            continue
                        row = {
                            "session_id": session_id,
                            "event_id": str(ev.get("eventId", f"evt-{secrets.token_hex(4)}")),
                            "timestamp": now_iso,
                            "event_type": str(ev.get("type", "unknown")),
                            "target_tag": str(ev.get("targetTag", "")),
                            "target_id": str(ev.get("targetId", "")),
                            "target_class": str(ev.get("targetClass", "")),
                            "target_selector": str(ev.get("targetSelector", "")),
                            "masked_value": str(ev.get("maskedValue", "")),
                            "payload": json.dumps(ev.get("payload", {})),
                            "trace_id": trace_id
                        }
                        json_rows.append(json.dumps(row))
                    if json_rows:
                        sql_evt_batch = "INSERT INTO default.rum_events FORMAT JSONEachRow\n" + "\n".join(json_rows) + "\n"
                        execute_clickhouse_query(sql_evt_batch)

            threading.Thread(target=persist_clickhouse, daemon=True).start()

            self.send_json(200, {
                "status": "accepted",
                "sessionId": session_id,
                "eventsProcessed": len(events),
                "piiRedacted": pii_redactions
            })
            return

        self.send_json(404, {"error": "not found"})


def run():
    server_address = ("", PORT)
    httpd = ThreadingHTTPServer(server_address, RUMRequestHandler)
    httpd.daemon_threads = True

    def handle_shutdown(signum, frame):
        sys.stderr.write(f"RUM collector received signal {signum}, shutting down cleanly...\n")
        try:
            httpd.server_close()
        except Exception:
            pass
        os._exit(0)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    sys.stderr.write(f"Argus RUM Collector & Replay Engine listening on port {PORT}...\n")
    httpd.serve_forever()

if __name__ == "__main__":
    run()
