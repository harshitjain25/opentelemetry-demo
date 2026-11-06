"""Inventory service (port 5002): answers 'is this item in stock?'"""
import random
import time

from flask import Flask, jsonify
from opentelemetry.instrumentation.flask import FlaskInstrumentor

from telemetry import setup_tracing

tracer = setup_tracing("inventory")
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)  # auto: one span per incoming HTTP request

STOCK = {"keyboard": 5, "mouse": 0, "monitor": 2}


@app.get("/stock/<item>")
def stock(item):
    # Manual span: wrap the "database lookup" so it shows up in the trace.
    with tracer.start_as_current_span("db.lookup_stock") as span:
        span.set_attribute("item", item)
        time.sleep(random.uniform(0.05, 0.3))  # pretend the DB is slow sometimes
        qty = STOCK.get(item, 0)
        span.set_attribute("quantity", qty)
    return jsonify(item=item, quantity=qty)


if __name__ == "__main__":
    app.run(port=5002)
