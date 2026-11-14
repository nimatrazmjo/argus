#!/usr/bin/env python3
"""Argus Shop — demo storefront (GUI) for the Argus demo mesh.

Dependency-free (stdlib only). Serves a single-page shop UI and proxies
/api/* to the mesh gateway, propagating W3C traceparent and emitting its own
root span (service.name=argus-storefront) so every click is one trace that
spans browser-facing edge -> gateway -> auth/catalog/order/...

Env: PORT, GATEWAY_URL, OTEL_EXPORTER_OTLP_ENDPOINT, SERVICE_NAME
"""
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8090"))
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://argus-svc-gateway:8001").rstrip("/")
OTLP = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://argus-gateway-collector.argus-system:4318").rstrip("/")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "argus-storefront")
POD_NAME = os.environ.get("POD_NAME", "local")
NAMESPACE = os.environ.get("POD_NAMESPACE", "demo")

# Injectable failures understood by the mesh (?trigger_error=...)
FAILURES = ["", "payment_declined", "auth_expired", "inventory_exhausted"]


def emit_span(trace_id, span_id, name, start_ns, end_ns, status, attrs):
    ok = status < 500
    payload = {"resourceSpans": [{
        "resource": {"attributes": [
            {"key": "service.name", "value": {"stringValue": SERVICE_NAME}},
            {"key": "deployment.environment", "value": {"stringValue": "production"}},
            {"key": "k8s.namespace.name", "value": {"stringValue": NAMESPACE}},
            {"key": "k8s.pod.name", "value": {"stringValue": POD_NAME}},
        ]},
        "scopeSpans": [{"scope": {"name": "argus.storefront"}, "spans": [{
            "traceId": trace_id, "spanId": span_id, "name": name, "kind": 2,
            "startTimeUnixNano": str(start_ns), "endTimeUnixNano": str(end_ns),
            "attributes": [{"key": k, "value": {"stringValue": str(v)}} for k, v in attrs.items()],
            "status": {"code": 1} if ok else {"code": 2, "message": f"HTTP {status}"},
        }]}],
    }]}

    def _send():
        try:
            req = urllib.request.Request(f"{OTLP}/v1/traces", data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=3).read()
        except Exception:
            pass
    threading.Thread(target=_send, daemon=True).start()


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Argus Shop</title>
<style>
:root{--bg:#0f1720;--card:#18222e;--ink:#e8eef5;--mute:#8ea0b3;--acc:#3ea6ff;--ok:#34c38f;--bad:#f1556c;--line:#263444}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;align-items:center;gap:16px;padding:14px 24px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--bg);z-index:5}
header h1{font-size:18px;margin:0}header .sp{flex:1}
button{font:inherit;border:0;border-radius:8px;padding:8px 14px;cursor:pointer;background:var(--acc);color:#04121f;font-weight:600}
button.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}button:disabled{opacity:.5;cursor:wait}
main{display:grid;grid-template-columns:1fr 320px;gap:24px;padding:24px;max-width:1200px;margin:auto}
@media(max-width:860px){main{grid-template-columns:1fr}}
h2{font-size:15px;color:var(--mute);text-transform:uppercase;letter-spacing:.06em;margin:0 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:6px}
.card .img{height:90px;border-radius:8px;background:linear-gradient(135deg,#1d3b57,#2a5d8f);display:grid;place-items:center;font-size:34px}
.price{font-weight:700}.sku{color:var(--mute);font-size:12px}
aside .panel{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin-bottom:16px}
.row{display:flex;justify-content:space-between;gap:8px;margin:6px 0}
select{width:100%;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:inherit}
.toast{position:fixed;right:20px;bottom:20px;max-width:380px;background:var(--card);border:1px solid var(--line);border-left:4px solid var(--ok);border-radius:10px;padding:12px 14px;display:none;z-index:9}
.toast.bad{border-left-color:var(--bad)}.toast code{display:block;word-break:break-all;background:var(--bg);padding:6px;border-radius:6px;margin-top:6px;font-size:12px;cursor:pointer}
.log{font:12px/1.5 ui-monospace,monospace;color:var(--mute);max-height:180px;overflow:auto}
.log .e{color:var(--bad)}.log .o{color:var(--ok)}
label.sw{display:flex;gap:8px;align-items:center;margin-top:10px;color:var(--mute)}
</style></head><body>
<header><h1>🛰️ Argus Shop</h1><span class="sp"></span>
<span id="who" style="color:var(--mute)">usr_9918</span>
<button class="ghost" id="cartBtn">Cart (<span id="cnt">0</span>)</button></header>
<main>
<section><h2>Catalog</h2><div class="grid" id="grid"></div>
<h2 style="margin-top:28px">Recommended for you</h2><div class="grid" id="recs"></div></section>
<aside>
<div class="panel"><h2>Cart</h2><div id="cart" style="color:var(--mute)">empty</div>
<div class="row"><b>Total</b><b id="total">$0.00</b></div>
<button id="co" style="width:100%" disabled>Checkout</button></div>
<div class="panel"><h2>Demo controls</h2>
<div style="color:var(--mute);font-size:13px;margin-bottom:6px">Inject failure into next requests</div>
<select id="fail"><option value="">None (healthy)</option>
<option value="payment_declined">Payment declined</option>
<option value="auth_expired">Auth token expired</option>
<option value="inventory_exhausted">Inventory exhausted</option></select>
<label class="sw"><input type="checkbox" id="auto"> Simulate shoppers (1 req/s)</label></div>
<div class="panel"><h2>Request log</h2><div class="log" id="log"></div></div>
</aside></main>
<div class="toast" id="toast"></div>
<script>
const $=s=>document.querySelector(s);let cart=[],items=[];
const emoji=["📡","🧩","🛡️","☁️","🔭","🔌"];
function log(m,c){const d=document.createElement('div');d.className=c||'';d.textContent=new Date().toLocaleTimeString()+' '+m;$('#log').prepend(d)}
function toast(html,bad){const t=$('#toast');t.className='toast'+(bad?' bad':'');t.innerHTML=html;t.style.display='block';clearTimeout(t._h);t._h=setTimeout(()=>t.style.display='none',9000);
 const c=t.querySelector('code');if(c)c.onclick=()=>navigator.clipboard&&navigator.clipboard.writeText(c.textContent)}
async function api(path){const f=$('#fail').value;const u=path+(f?(path.includes('?')?'&':'?')+'trigger_error='+f:'');
 const r=await fetch(u);let j={};try{j=await r.json()}catch(e){}return{ok:r.ok,status:r.status,j,trace:r.headers.get('X-Trace-Id')||j.trace_id||''}}
function card(p,i,add){const d=document.createElement('div');d.className='card';
 d.innerHTML=`<div class="img">${emoji[i%emoji.length]}</div><b>${p.name}</b><span class="sku">${p.sku}</span>`+
 (p.price!=null?`<span class="price">$${p.price.toFixed(2)}</span>`:`<span class="sku">affinity ${p.affinity}</span>`)+(add?'<button>Add to cart</button>':'');
 if(add)d.querySelector('button').onclick=()=>{cart.push(p);render()};return d}
function render(){$('#cnt').textContent=cart.length;$('#co').disabled=!cart.length;
 $('#cart').innerHTML=cart.length?cart.map(p=>`<div class="row"><span>${p.name}</span><span>$${p.price.toFixed(2)}</span></div>`).join(''):'empty';
 $('#total').textContent='$'+cart.reduce((a,p)=>a+p.price,0).toFixed(2)}
async function load(){const r=await api('/api/search');log(`GET /api/search -> ${r.status}`,r.ok?'o':'e');
 if(!r.ok){toast(`Catalog failed (${r.status})<code>${r.trace}</code>`,true);return}
 items=r.j.items||[];$('#grid').replaceChildren(...items.map((p,i)=>card(p,i,true)));
 $('#recs').replaceChildren(...(r.j.recommendations||[]).map((p,i)=>card(p,i+2,false)))}
$('#co').onclick=async()=>{const b=$('#co');b.disabled=true;b.textContent='Processing…';
 const r=await api('/api/checkout');log(`POST /api/checkout -> ${r.status} trace=${r.trace.slice(0,8)}`,r.ok?'o':'e');
 if(r.ok){toast(`✅ Order placed<br>Trace ID (click to copy, search in SigNoz):<code>${r.trace}</code>`);cart=[]}
 else toast(`❌ Checkout failed (${r.status}): ${(r.j.message||r.j.error||'error')}<br>Trace ID:<code>${r.trace}</code>`,true);
 b.textContent='Checkout';render()};
let timer=null;$('#auto').onchange=e=>{clearInterval(timer);if(e.target.checked)timer=setInterval(async()=>{
 const x=Math.random();const r=await api(x<.6?'/api/search':'/api/checkout');log(`sim ${r.status}`,r.ok?'o':'e')},1000)};
$('#cartBtn').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
load();render();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "ArgusShop/1.0"

    def log_message(self, fmt, *args):  # quiet healthz noise
        if "/healthz" not in (args[0] if args else ""):
            super().log_message(fmt, *args)

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/healthz":
            return self._send(200, '{"status":"healthy"}')
        if parsed.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if parsed.path.startswith("/api/"):
            return self._proxy(parsed)
        self._send(404, '{"error":"not found"}')

    do_POST = do_GET

    def _proxy(self, parsed):
        trace_id, span_id = secrets.token_hex(16), secrets.token_hex(8)
        start = time.time_ns()
        url = f"{GATEWAY_URL}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
        req = urllib.request.Request(url, headers={"traceparent": f"00-{trace_id}-{span_id}-01"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                code, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            code, body = e.code, e.read()
        except Exception as e:
            code, body = 502, json.dumps({"error": type(e).__name__, "message": str(e)}).encode()
        # ensure the UI always has the trace id, even on mesh errors
        try:
            j = json.loads(body)
            if isinstance(j, dict) and "trace_id" not in j and code >= 500:
                j["trace_id"] = trace_id
                body = json.dumps(j).encode()
        except Exception:
            pass
        emit_span(trace_id, span_id, f"GET {parsed.path}", start, time.time_ns(), code,
                  {"http.method": "GET", "http.target": parsed.path, "http.status_code": code,
                   "demo.trigger_error": urllib.parse.parse_qs(parsed.query).get("trigger_error", [""])[0]})
        self._send(code, body, extra={"X-Trace-Id": trace_id})


if __name__ == "__main__":
    print(f"{SERVICE_NAME} on :{PORT} -> {GATEWAY_URL}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
