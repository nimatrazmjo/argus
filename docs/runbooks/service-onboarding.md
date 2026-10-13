# Argus Platform Runbook: Zero-Code Service Onboarding

**Target Audience**: Application Developers, Platform Engineers, DHS DevSecOps Teams  
**Feature Reference**: F007 — Zero-Code Auto-Instrumentation via OpenTelemetry Operator  
**Platform Version**: Argus v1.0 (Air-Gapped)

---

## 1. Overview & Architecture

Argus provides automatic, zero-code distributed tracing and metrics for containerized workloads running on Kubernetes. Through the OpenTelemetry Operator and Mutating Admission Webhook, application pods are automatically injected with the appropriate language runtime agent when annotated.

### Zero-Code Architecture
```
+-------------------------------------------------------------+
| Kubernetes Pod (e.g. argus-system / application namespace)   |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Init Container (Injected by Webhook)                  |  |
|  | localhost:5001/argus/autoinstrumentation-<lang>       |  |
|  | -> Copies OTel agent bundle into emptyDir volume      |  |
|  +-------------------------------------------------------+  |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Application Container (ZERO CODE CHANGES)             |  |
|  | - Injected PYTHONPATH / CLASSPATH / NODE_OPTIONS      |  |
|  | - Injected OTEL_EXPORTER_OTLP_ENDPOINT                |  |
|  | - Injected Kubernetes resource metadata attributes    |  |
|  +---------------------------+---------------------------+  |
+------------------------------|------------------------------+
                               | OTLP (HTTP/gRPC)
                               v
+-------------------------------------------------------------+
| Argus OTel Gateway Collector (PII / CJIS Redaction Pipeline)  |
+------------------------------+------------------------------+
                               v
+-------------------------------------------------------------+
| ClickHouse HA Cluster & SigNoz APM UI                       |
+-------------------------------------------------------------+
```

---

## 2. The One-Line Onboarding Step

To onboard any new or existing service, add a **single annotation** to the Pod template metadata (`spec.template.metadata.annotations`) in your Kubernetes `Deployment`, `StatefulSet`, or `DaemonSet`.

### Supported Languages & Annotations

| Runtime | Pod Annotation | Injected Mirror Image |
| :--- | :--- | :--- |
| **Python** (Flask, FastAPI, Django, Tornado, WSGI, ASGI) | `instrumentation.opentelemetry.io/inject-python: "true"` | `localhost:5001/argus/autoinstrumentation-python:0.65b0` |
| **Node.js** (Express, Fastify, NestJS, HTTP) | `instrumentation.opentelemetry.io/inject-nodejs: "true"` | `localhost:5001/argus/autoinstrumentation-nodejs:0.78.0` |
| **Java** (Spring Boot, Quarkus, Micronaut, Tomcat) | `instrumentation.opentelemetry.io/inject-java: "true"` | `localhost:5001/argus/autoinstrumentation-java:2` |

> **Note**: If your application is in a namespace that uses the central platform instrumentation, you can specify either `"true"` or `"argus-system/argus-instrumentation"`.

---

## 3. Step-by-Step Deployment Example

### Python Microservice Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-service
  namespace: argus-system
  labels:
    app.kubernetes.io/name: payment-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app.kubernetes.io/name: payment-service
  template:
    metadata:
      labels:
        app.kubernetes.io/name: payment-service
      annotations:
        # --> SINGLE LINE REQUIRED FOR ARGUS AUTO-INSTRUMENTATION <--
        instrumentation.opentelemetry.io/inject-python: "true"
    spec:
      containers:
        - name: payment-service
          image: localhost:5001/argus/payment-service:1.0.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 250m
              memory: 256Mi
```

### Deploying & Triggering Rollout
```bash
# 1. Apply the updated manifest
kubectl apply -f deploy/payment-service.yaml

# 2. Monitor rollout
kubectl rollout status deployment/payment-service -n argus-system

# 3. Verify injection
kubectl get pod -l app.kubernetes.io/name=payment-service -o jsonpath='{.items[0].spec.initContainers[*].name}'
# Expected output: opentelemetry-auto-instrumentation-python
```

---

## 4. Automatic Context & Enrichment

When injected, Argus automatically decorates every transaction, trace span, and metric with Kubernetes topology attributes:
- `service.name`: Derived from container or deployment name (can be overridden via `OTEL_SERVICE_NAME`).
- `k8s.pod.name`: Name of the executing pod.
- `k8s.namespace.name`: Namespace where workload is deployed.
- `k8s.node.name`: Worker node hosting the pod.
- `k8s.container.name`: Name of the application container.

All outgoing HTTP/gRPC requests automatically carry W3C `traceparent` headers (`tracecontext`, `baggage`, `b3`), ensuring end-to-end distributed trace propagation across downstream services without developer intervention.

---

## 5. Verification in SigNoz UI

1. Open the SigNoz web dashboard:
   ```bash
   kubectl -n argus-system port-forward svc/signoz 8080:8080
   # Open browser at http://localhost:8080
   ```
2. Navigate to **Services**:
   - Verify your service appears in the APM service catalog (e.g. `payment-service` or `argus-auto-service`).
   - Click on the service to view:
     - Request rate (RPS)
     - Error rate percentage
     - P50, P90, P99 latency graphs
     - Auto-generated Service Map
3. Navigate to **Traces**:
   - Filter by `serviceName = "<your-service>"`.
   - Inspect waterfall trace diagrams showing inbound HTTP spans and outbound client dependency calls.

---

## 6. Edge Cases, Troubleshooting & FAQs

### Q1: What happens if an unsupported language annotation is provided?
**Answer**: If an unrecognized or unsupported annotation is present (e.g., `inject-ruby: "true"`), the OpenTelemetry Operator mutating webhook simply ignores the annotation. The pod deploys normally without disruption or crash loops.

### Q2: What happens if there is an annotation typo?
**Answer**: If an invalid `Instrumentation` CR name is specified (e.g. `inject-python: "non-existent"`), Kubernetes will not inject the agent and the pod will start normally without instrumentation. Existing running workloads are completely unaffected.

### Q3: What happens if the Argus OTel Gateway is temporarily unreachable?
**Answer**: The auto-instrumentation SDK employs an asynchronous, non-blocking batch exporter (`BatchSpanProcessor`). If the collector drops or is partitioned, spans are dropped silently in memory after the queue buffer is full. Your application never crashes, blocks, or drops HTTP transactions due to observability outages.

### Q4: Can I override the service name?
**Answer**: Yes. Add an explicit environment variable to your container spec:
```yaml
env:
  - name: OTEL_SERVICE_NAME
    value: "custom-service-name"
```

### Q5: How are sensitive fields (SSN, credit cards) handled?
**Answer**: The Argus platform spine routes all telemetry through the OpenTelemetry Gateway redaction processor before storing in ClickHouse. Sensitive patterns (SSNs, CJIS identifiers, Bearer tokens) are masked at ingest.
