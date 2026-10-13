from flask import Flask, jsonify, request
import urllib.request
import os

app = Flask("argus-auto-service")

@app.route("/healthz")
def healthz():
    return jsonify(status="healthy", mode="zero-code-auto-instrumented")

@app.route("/api/order", methods=["GET", "POST"])
def order():
    order_id = request.args.get("order_id", "AUTO-1001")
    # Downstream call using standard library urllib — auto-instrumented as child span!
    downstream_status = "skipped"
    try:
        with urllib.request.urlopen("http://argus-sample-service.argus-system:8080/healthz", timeout=2) as resp:
            downstream_status = f"http_{resp.status}"
    except Exception as e:
        downstream_status = f"err_{type(e).__name__}"

    return jsonify(
        order_id=order_id,
        status="PROCESSED",
        service="argus-auto-service",
        downstream=downstream_status,
        auto_instrumented=True
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
