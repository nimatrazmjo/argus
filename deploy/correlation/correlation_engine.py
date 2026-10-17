#!/usr/bin/env python3
"""
Argus Topological Alert Correlation & Root-Cause Grouping Engine
Listens on port 9097 in argus-system.
Clusters temporally co-occurring alerts based on service topology (F007/F008),
performs multi-factor probable-cause ranking, calculates blast radius,
and emits single consolidated incident tickets to ServiceNow Table API.
"""

import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading

PORT = int(os.environ.get("PORT", "9097"))
SERVICENOW_URL = os.environ.get(
    "SERVICENOW_URL", "http://argus-servicenow-mock.argus-system.svc.cluster.local:8088/api/now/table/incident"
).rstrip("/")
CORRELATION_WINDOW_SECONDS = int(os.environ.get("CORRELATION_WINDOW_SECONDS", "120"))

# Thread-safe locks
LOCK = threading.Lock()

# Default Seed Topology Graph (F007 auto-instrumentation & F008 eBPF service maps)
# caller -> callee (caller depends on callee)
DEFAULT_EDGES = [
    {"source": "argus-synthetic-probe", "target": "argus-auto-service", "relation": "probes"},
    {"source": "argus-rum-collector", "target": "argus-auto-service", "relation": "ingests_for"},
    {"source": "argus-auto-service", "target": "argus-sample-service", "relation": "calls"},
    {"source": "argus-sample-service", "target": "chi-argus-clickhouse", "relation": "queries"},
    # Isolated microservice track (for anti-false-merge validation)
    {"source": "argus-payment-service", "target": "argus-postgres-db", "relation": "calls"},
    # Isolated identity track
    {"source": "argus-auth-service", "target": "argus-idp", "relation": "validates_with"}
]

class TopologyGraph:
    """Manages service topology DAG and reachability queries."""
    def __init__(self):
        self.edges = []
        self.callers_of = {} # callee -> set(callers)
        self.callees_of = {} # caller -> set(callees)
        self.nodes = set()
        self.reset_to_default()

    def reset_to_default(self):
        self.edges = []
        self.callers_of = {}
        self.callees_of = {}
        self.nodes = set()
        for e in DEFAULT_EDGES:
            self.add_edge(e["source"], e["target"], e.get("relation", "calls"))

    def add_edge(self, source: str, target: str, relation: str = "calls"):
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges.append({"source": source, "target": target, "relation": relation})
        if target not in self.callers_of:
            self.callers_of[target] = set()
        self.callers_of[target].add(source)
        if source not in self.callees_of:
            self.callees_of[source] = set()
        self.callees_of[source].add(target)

    def get_callees(self, node: str) -> set:
        """Services directly called by `node` (upstream dependencies of node)."""
        return self.callees_of.get(node, set())

    def get_callers(self, node: str) -> set:
        """Services that call `node` (downstream clients of node)."""
        return self.callers_of.get(node, set())

    def get_all_callees(self, node: str, visited=None) -> set:
        """Transitive dependencies called by `node`."""
        if visited is None:
            visited = set()
        res = set()
        for c in self.get_callees(node):
            if c not in visited:
                visited.add(c)
                res.add(c)
                res.update(self.get_all_callees(c, visited))
        return res

    def get_all_callers(self, node: str, visited=None) -> set:
        """Transitive callers dependent on `node` (blast radius)."""
        if visited is None:
            visited = set()
        res = set()
        for c in self.get_callers(node):
            if c not in visited:
                visited.add(c)
                res.add(c)
                res.update(self.get_all_callers(c, visited))
        return res

    def are_connected(self, svc1: str, svc2: str) -> bool:
        """Checks if svc1 and svc2 have any causal/topological reachability or shared dependency."""
        if svc1 == svc2:
            return True
        # Check direct or transitive reachability in either direction
        if svc2 in self.get_all_callees(svc1) or svc1 in self.get_all_callees(svc2):
            return True
        if svc2 in self.get_all_callers(svc1) or svc1 in self.get_all_callers(svc2):
            return True
        # Check if they share a common failure dependency or common caller
        shared_callees = self.get_all_callees(svc1).intersection(self.get_all_callees(svc2))
        if shared_callees:
            return True
        return False

    def find_shortest_causal_path(self, root: str, symptom: str) -> list:
        """Finds directed path from root to symptom along the caller chain."""
        if root == symptom:
            return [root]
        queue = [[root]]
        visited = set([root])
        while queue:
            path = queue.pop(0)
            node = path[-1]
            for neighbor in self.get_callers(node):
                if neighbor == symptom:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])
        return [root, symptom]

TOPOLOGY = TopologyGraph()
INCIDENT_GROUPS = {} # incident_id -> IncidentCluster dict
STATS = {
    "alerts_received": 0,
    "incidents_created": 0,
    "alerts_correlated": 0,
    "alerts_isolated": 0,
    "servicenow_dispatches": 0,
    "servicenow_updates": 0,
    "incidents_resolved": 0
}

def normalize_service_name(svc: str) -> str:
    """Normalizes service names from labels (handles port suffixes, pod names)."""
    if not svc:
        return "unknown"
    s = svc.lower().strip()
    if s.startswith("service/") or s.startswith("deployment/"):
        s = s.split("/", 1)[1]
    if ":" in s:
        s = s.split(":", 1)[0]
    return s

def calculate_criticality_weight(alertname: str, labels: dict) -> float:
    """Computes failure criticality weight based on failure type."""
    name = (alertname + " " + json.dumps(labels)).lower()
    if any(k in name for k in ["database", "connection", "clickhouse", "postgres", "pool", "disk", "oom", "crash"]):
        return 1.0
    if any(k in name for k in ["5xx", "500", "errorrate", "high5xx", "http_5", "exception"]):
        return 0.75
    if any(k in name for k in ["timeout", "latency", "highlatency", "slow"]):
        return 0.50
    if any(k in name for k in ["synthetic", "probe", "canary", "rum", "browser"]):
        return 0.30
    return 0.50

def rank_cluster_root_cause(alerts: list, topology: TopologyGraph) -> tuple[dict, list, list]:
    """
    Evaluates multi-factor probable-cause ranking across all alerts in an incident cluster:
    Score = 0.50 * TopoRank + 0.30 * TimePrecedence + 0.20 * CriticalityWeight.
    Returns (probable_root_cause, symptoms, causal_path).
    """
    if not alerts:
        return {}, [], []

    # 1. Topological Depth: A service that doesn't depend on any other FAILING service in the cluster
    # is the upstream root of the failure cascade!
    failing_services = set(a["service"] for a in alerts)
    
    # Earliest timestamp for relative time scoring
    timestamps = [a["timestamp"] for a in alerts]
    min_time = min(timestamps) if timestamps else time.time()
    max_time = max(timestamps) if timestamps else min_time
    time_span = max(max_time - min_time, 1.0)

    scored_alerts = []
    for a in alerts:
        svc = a["service"]
        all_callees = topology.get_all_callees(svc)
        failing_dependencies = all_callees.intersection(failing_services)
        
        # Topological score:
        # 1.0 if has 0 failing upstream dependencies (it is the root callee of the cascade!)
        # Penalized to <= 0.3 if it depends on another service in the failure set
        if not failing_dependencies:
            topo_score = 1.0
        else:
            topo_score = max(0.1, 0.35 - (0.05 * len(failing_dependencies)))

        # Time precedence score: 1.0 for first alert to fire
        time_diff = a["timestamp"] - min_time
        time_score = max(0.1, 1.0 - (0.6 * (time_diff / time_span)))

        # Criticality weight
        crit_score = calculate_criticality_weight(a["alertname"], a.get("labels", {}))

        total_score = (0.50 * topo_score) + (0.30 * time_score) + (0.20 * crit_score)
        scored_alerts.append({
            "alert": a,
            "score": round(total_score, 4),
            "topo_score": round(topo_score, 3),
            "time_score": round(time_score, 3),
            "crit_score": round(crit_score, 3)
        })

    # Sort descending by total score
    scored_alerts.sort(key=lambda x: x["score"], reverse=True)
    top = scored_alerts[0]
    root_alert = top["alert"]

    # Compute confidence
    if len(scored_alerts) > 1:
        second_score = scored_alerts[1]["score"]
        margin = top["score"] - second_score
        confidence = min(0.99, max(0.85, round(0.85 + (0.35 * margin), 3)))
    else:
        confidence = 0.95

    probable_root_cause = {
        "service": root_alert["service"],
        "alertname": root_alert["alertname"],
        "confidence": confidence,
        "score": top["score"],
        "startsAt": root_alert.get("startsAt", ""),
        "timestamp": root_alert["timestamp"],
        "reason": f"Topological root dependency in failure graph with high failure criticality ({top['crit_score']}) and causal precedence."
    }

    # Format symptoms
    symptoms = []
    root_svc = root_alert["service"]
    for item in scored_alerts[1:]:
        al = item["alert"]
        s_svc = al["service"]
        path = topology.find_shortest_causal_path(root_svc, s_svc)
        hops = len(path) - 1
        symptoms.append({
            "service": s_svc,
            "alertname": al["alertname"],
            "score": item["score"],
            "hops_from_root": max(1, hops),
            "startsAt": al.get("startsAt", ""),
            "timestamp": al["timestamp"],
            "relation_to_root": f"{hops}-hop downstream caller affected by cascade"
        })

    # Overall causal cascade path
    causal_path = [root_svc]
    for sym in symptoms:
        if sym["service"] not in causal_path:
            causal_path.append(sym["service"])

    return probable_root_cause, symptoms, causal_path

def send_to_servicenow(payload: dict, method: str = "POST", url: str = None) -> tuple[bool, dict]:
    """Issues an HTTP request to ServiceNow Table API."""
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

class CorrelationHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
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
        global TOPOLOGY, INCIDENT_GROUPS, STATS
        if self.path == "/healthz" or self.path == "/health":
            self._send_json(200, {
                "status": "ok",
                "service": "argus-correlation-engine",
                "version": "1.0.0",
                "timestamp": time.time()
            })
            return

        if self.path == "/api/status":
            with LOCK:
                active_count = sum(1 for inc in INCIDENT_GROUPS.values() if inc.get("status") == "firing")
                self._send_json(200, {
                    "status": "healthy",
                    "active_incidents": active_count,
                    "total_incidents": len(INCIDENT_GROUPS),
                    "topology_nodes_count": len(TOPOLOGY.nodes),
                    "topology_edges_count": len(TOPOLOGY.edges),
                    "stats": dict(STATS)
                })
            return

        if self.path == "/api/topology":
            with LOCK:
                self._send_json(200, {
                    "nodes": sorted(list(TOPOLOGY.nodes)),
                    "edges": TOPOLOGY.edges
                })
            return

        if self.path == "/api/incidents":
            with LOCK:
                inc_list = list(INCIDENT_GROUPS.values())
                self._send_json(200, {"incidents": inc_list, "total": len(inc_list)})
            return

        if self.path.startswith("/api/incidents/"):
            inc_id = self.path.split("/api/incidents/")[1].strip()
            with LOCK:
                if inc_id in INCIDENT_GROUPS:
                    self._send_json(200, INCIDENT_GROUPS[inc_id])
                    return
            self._send_json(404, {"error": f"Incident {inc_id} not found"})
            return

        if self.path == "/metrics":
            with LOCK:
                reduction_ratio = 0.0
                if STATS["alerts_received"] > 0:
                    reduction_ratio = round((STATS["alerts_received"] - STATS["incidents_created"]) / STATS["alerts_received"], 4)
                
                output = [
                    "# HELP argus_correlation_alerts_received_total Total alert events ingested",
                    "# TYPE argus_correlation_alerts_received_total counter",
                    f'argus_correlation_alerts_received_total {STATS["alerts_received"]}',
                    "# HELP argus_correlation_incidents_created_total Total correlated incident tickets created",
                    "# TYPE argus_correlation_incidents_created_total counter",
                    f'argus_correlation_incidents_created_total {STATS["incidents_created"]}',
                    "# HELP argus_correlation_alerts_grouped_total Alerts grouped into existing incidents",
                    "# TYPE argus_correlation_alerts_grouped_total counter",
                    f'argus_correlation_alerts_grouped_total {STATS["alerts_correlated"]}',
                    "# HELP argus_correlation_reduction_ratio Alert storm suppression ratio",
                    "# TYPE argus_correlation_reduction_ratio gauge",
                    f'argus_correlation_reduction_ratio {reduction_ratio}'
                ]
            body = "\n".join(output) + "\n"
            try:
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        global TOPOLOGY, INCIDENT_GROUPS, STATS
        content_len = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else ""

        if self.path == "/api/reset":
            with LOCK:
                INCIDENT_GROUPS.clear()
                TOPOLOGY.reset_to_default()
                for k in STATS:
                    STATS[k] = 0
            self._send_json(200, {"status": "reset_successful"})
            return

        if self.path == "/api/topology":
            if not raw_body:
                self._send_json(400, {"error": "Missing payload"})
                return
            try:
                data = json.loads(raw_body)
                src = data.get("source")
                tgt = data.get("target")
                rel = data.get("relation", "calls")
                if not src or not tgt:
                    self._send_json(400, {"error": "source and target required"})
                    return
                with LOCK:
                    TOPOLOGY.add_edge(src, tgt, rel)
                self._send_json(200, {"status": "edge_added", "edge": {"source": src, "target": tgt, "relation": rel}})
            except Exception as e:
                self._send_json(400, {"error": str(e)})
            return

        if self.path == "/api/topology/reset":
            with LOCK:
                TOPOLOGY.reset_to_default()
            self._send_json(200, {"status": "topology_reset_to_default"})
            return

        if self.path in ("/webhook/alert", "/api/alerts", "/v1/alerts"):
            if not raw_body:
                self._send_json(400, {"error": "Empty body"})
                return
            try:
                payload = json.loads(raw_body)
            except Exception as e:
                self._send_json(400, {"error": f"Invalid JSON: {str(e)}"})
                return

            alerts_raw = payload.get("alerts", [])
            if not alerts_raw and "labels" in payload:
                alerts_raw = [payload]

            now = time.time()
            results = []

            for raw_al in alerts_raw:
                labels = raw_al.get("labels", {})
                annotations = raw_al.get("annotations", {})
                alertname = labels.get("alertname", "UnknownAlert")
                raw_service = labels.get("service", labels.get("job", labels.get("app", "unknown")))
                service = normalize_service_name(raw_service)
                tenant_id = labels.get("tenant_id", "default")
                status = raw_al.get("status", "firing").lower()
                severity = labels.get("severity", "warning").lower()
                fingerprint = raw_al.get("fingerprint", "")
                if not fingerprint:
                    import hashlib
                    fingerprint = hashlib.sha256(f"{alertname}:{service}:{tenant_id}:{json.dumps(labels)}".encode()).hexdigest()[:16]

                parsed_alert = {
                    "fingerprint": fingerprint,
                    "alertname": alertname,
                    "service": service,
                    "tenant_id": tenant_id,
                    "status": status,
                    "severity": severity,
                    "startsAt": raw_al.get("startsAt", ""),
                    "timestamp": now,
                    "labels": labels,
                    "annotations": annotations
                }

                with LOCK:
                    STATS["alerts_received"] += 1

                # 1. Handle Alert Resolution
                if status == "resolved":
                    resolved_inc_id = None
                    with LOCK:
                        for inc_id, inc in list(INCIDENT_GROUPS.items()):
                            for a in inc["alerts"]:
                                if a["fingerprint"] == fingerprint:
                                    a["status"] = "resolved"
                                    # Check if all alerts in this group resolved
                                    if all(x.get("status") == "resolved" for x in inc["alerts"]):
                                        inc["status"] = "resolved"
                                        inc["resolved_at"] = now
                                        resolved_inc_id = inc_id
                                        STATS["incidents_resolved"] += 1
                                    break
                    if resolved_inc_id:
                        # Sync resolution to ServiceNow (state 6 = Resolved)
                        inc = INCIDENT_GROUPS[resolved_inc_id]
                        if inc.get("servicenow_sys_id"):
                            send_to_servicenow({"state": "6", "close_notes": "All correlated alerts resolved"},
                                               method="PATCH",
                                               url=f"{SERVICENOW_URL}/{inc['servicenow_sys_id']}")
                        results.append({"fingerprint": fingerprint, "action": "resolved_and_closed_incident", "incident_id": resolved_inc_id})
                    else:
                        results.append({"fingerprint": fingerprint, "action": "alert_marked_resolved"})
                    continue

                # 2. Correlate with Existing Active Incidents
                matched_incident_id = None
                with LOCK:
                    for inc_id, inc in INCIDENT_GROUPS.items():
                        if inc.get("status") != "firing":
                            continue
                        # Tenant isolation guardrail: Never merge cross-tenant incidents
                        if inc.get("tenant_id") != tenant_id:
                            continue
                        # Time window check: Must be within correlation window
                        if now - inc["created_at"] > CORRELATION_WINDOW_SECONDS:
                            continue

                        # Topological connectivity check:
                        # Alert service must be connected to at least one service in the incident
                        incident_services = set(a["service"] for a in inc["alerts"])
                        if any(TOPOLOGY.are_connected(service, existing_svc) for existing_svc in incident_services):
                            matched_incident_id = inc_id
                            break

                if matched_incident_id:
                    # Append alert to existing incident cluster and re-rank
                    with LOCK:
                        inc = INCIDENT_GROUPS[matched_incident_id]
                        # Check duplicate alert within same cluster
                        if not any(a["fingerprint"] == fingerprint for a in inc["alerts"]):
                            inc["alerts"].append(parsed_alert)
                            STATS["alerts_correlated"] += 1
                        inc["updated_at"] = now

                        # Re-evaluate probable root cause and blast radius
                        root_cause, symptoms, causal_path = rank_cluster_root_cause(inc["alerts"], TOPOLOGY)
                        inc["probable_root_cause"] = root_cause
                        inc["symptoms"] = symptoms
                        inc["causal_path"] = causal_path
                        inc["blast_radius"] = sorted(list(set(a["service"] for a in inc["alerts"] if a["service"] != root_cause["service"])))

                        sys_id = inc.get("servicenow_sys_id")

                    # Update ServiceNow ticket with work notes (avoiding duplicate page)
                    if sys_id:
                        update_payload = {
                            "short_description": f"[ARGUS CORRELATED] Root Cause: {root_cause['service']} ({root_cause['alertname']}) - {len(symptoms)} symptoms grouped",
                            "work_notes": f"[CORRELATION ENGINE UPDATE] Correlated alert '{alertname}' on service '{service}'. Blast radius: {len(inc['blast_radius'])} services. Probable root cause: {root_cause['service']} (confidence: {root_cause['confidence'] * 100:.1f}%)."
                        }
                        send_to_servicenow(update_payload, method="PATCH", url=f"{SERVICENOW_URL}/{sys_id}")
                        with LOCK:
                            STATS["servicenow_updates"] += 1

                    results.append({
                        "fingerprint": fingerprint,
                        "action": "correlated_into_existing_incident",
                        "incident_id": matched_incident_id,
                        "probable_root_cause": root_cause["service"],
                        "total_alerts_in_incident": len(inc["alerts"]),
                        "servicenow_number": inc.get("servicenow_number")
                    })

                else:
                    # Create New Incident Cluster
                    inc_id = f"INC-CORR-{int(now)}-{uuid.uuid4().hex[:6]}"
                    root_cause, symptoms, causal_path = rank_cluster_root_cause([parsed_alert], TOPOLOGY)
                    new_incident = {
                        "incident_id": inc_id,
                        "created_at": now,
                        "updated_at": now,
                        "status": "firing",
                        "tenant_id": tenant_id,
                        "alerts": [parsed_alert],
                        "probable_root_cause": root_cause,
                        "symptoms": symptoms,
                        "causal_path": causal_path,
                        "blast_radius": [],
                        "servicenow_sys_id": None,
                        "servicenow_number": None
                    }

                    # Prepare ServiceNow Table API Payload
                    sn_payload = {
                        "short_description": f"[ARGUS CORRELATED] Root Cause: {service} ({alertname})",
                        "description": f"Argus Correlated Incident {inc_id}\nProbable Root Cause: {service}\nAlert: {alertname}\nTimestamp: {now}\nCausal Path: {' -> '.join(causal_path)}\nLabels: {json.dumps(labels)}",
                        "urgency": "1" if severity == "critical" else "2",
                        "impact": "1",
                        "priority": "1" if severity == "critical" else "2",
                        "category": "Application",
                        "correlation_id": inc_id,
                        "state": "1", # New
                        "assignment_group": "DHS-Argus-SRE",
                        "work_notes": f"Incident generated by Argus Topological Correlation Engine. Initial alert: {alertname} on {service}."
                    }

                    success, sn_resp = send_to_servicenow(sn_payload, method="POST")
                    if success:
                        rec = sn_resp.get("result", {})
                        new_incident["servicenow_sys_id"] = rec.get("sys_id")
                        new_incident["servicenow_number"] = rec.get("number")
                        with LOCK:
                            STATS["servicenow_dispatches"] += 1

                    with LOCK:
                        INCIDENT_GROUPS[inc_id] = new_incident
                        STATS["incidents_created"] += 1
                        STATS["alerts_isolated"] += 1

                    results.append({
                        "fingerprint": fingerprint,
                        "action": "created_new_incident",
                        "incident_id": inc_id,
                        "probable_root_cause": service,
                        "servicenow_number": new_incident.get("servicenow_number")
                    })

            self._send_json(200, {
                "status": "processed",
                "processed_count": len(results),
                "results": results
            })
            return

        self._send_json(404, {"error": "Not Found"})

def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), CorrelationHandler)
    server.daemon_threads = True
    print(f"[Correlation-Engine] Listening on port {PORT}...")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
