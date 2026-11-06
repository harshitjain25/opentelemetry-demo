"""Orders service (port 5001): places an order, asking Inventory first."""
import time

import requests
from flask import Flask, jsonify
from opentelemetry import trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

from telemetry import setup_tracing

tracer = setup_tracing("orders")
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)  # auto: span per incoming request
RequestsInstrumentor().instrument()       # auto: span per outgoing call + injects
                                          # the `traceparent` header (context propagation!)


@app.post("/order/<item>")
def order(item):
    with tracer.start_as_current_span("check_inventory"):
        r = requests.get(f"http://localhost:5002/stock/{item}")
        qty = r.json()["quantity"]

    if qty == 0:
        span = trace.get_current_span()
        span.set_status(trace.Status(trace.StatusCode.ERROR, "out of stock"))
        span.add_event("order_rejected", {"item": item})
        return jsonify(error=f"{item} is out of stock"), 409

    with tracer.start_as_current_span("charge_payment") as span:
        span.set_attribute("payment.amount_inr", 1999)
        time.sleep(0.1)

    return jsonify(status="ordered", item=item)


if __name__ == "__main__":
    app.run(port=5001)
