# Learning OpenTelemetry: a weekend guide

## Part 1: The problem (read this first)

Imagine a user clicks **"Buy"** and it takes 4 seconds. Your backend is 6 microservices.
Which one is slow? Each service has its own logs, on different machines, with no link between them.

**Observability** means being able to answer "what is my system doing, and why?" from the outside.
It rests on 3 "signals":

| Signal | Answers | Example |
|---|---|---|
| **Traces** | *Where* did the time go in one request? | `POST /order` → `check_inventory` (250ms) → `db.lookup` (245ms) |
| **Metrics** | *How much / how often*, overall? | p99 latency = 800ms, 2% error rate |
| **Logs** | *What exactly* happened at one moment? | `"payment failed: card declined"` |

**What OpenTelemetry (OTel) is:** a vendor-neutral, open standard (a CNCF project, like Kubernetes)
for *producing* and *shipping* that data. You instrument your code once with OTel, then send the
data to **any** backend: Jaeger, Grafana, Datadog, Honeycomb, New Relic. Before OTel, every vendor had
its own SDK, and switching vendors meant re-instrumenting everything.

> One-liner for your post: **"OTel is the USB-C of observability."** You plug in once and it works with any backend.

**What OTel is NOT:** it is not a dashboard or a database. It doesn't store or display anything. That's the backend's job.

## Part 2: The 6 concepts you actually need

1. **Span**: one unit of work with a start time, an end time, a name, and attributes.
   For example, "db.lookup_stock took 245ms, item=mouse".
2. **Trace**: a tree of spans that all belong to one request, linked by one shared **trace_id**.
3. **Parent/child**: each span stores its parent's span_id. That's how the tree (the "waterfall") is built.
4. **Context propagation**: when Service A calls Service B, A sends the trace_id in an HTTP header
   called `traceparent` (a W3C standard). B reads it and continues the *same* trace.
   **This is the magic trick of distributed tracing.**
5. **Instrumentation**:
   - *Auto*: libraries create spans for you (every Flask request, every `requests` call).
   - *Manual*: you add `tracer.start_as_current_span("...")` around business logic you care about.
6. **Exporter / Collector**: the exporter sends spans somewhere (here, your terminal). In production,
   apps usually send to an **OTel Collector**, a separate process that batches, filters, and forwards
   data to one or more backends.

## Part 3: The demo in this folder

```
 curl ──► orders (5001) ──HTTP + traceparent header──► inventory (5002)
           ├─ check_inventory                            └─ db.lookup_stock (slow!)
           └─ charge_payment
```

| File | What to look at |
|---|---|
| `telemetry.py` | The setup: Resource, TracerProvider, Exporter. It's the same boilerplate in every OTel app. |
| `orders.py` | Auto-instrumentation (Flask + requests), manual spans, error status, span events |
| `inventory.py` | Receives the propagated context, plus a manual "DB" span |

### Set up (one time)

```bash
git clone https://github.com/harshitjain25/opentelemetry-demo.git
cd opentelemetry-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run it (3 terminal tabs)

In each tab, first run `cd opentelemetry-demo && source .venv/bin/activate`, then:

```bash
python inventory.py        # tab 1
python orders.py           # tab 2
curl -X POST localhost:5001/order/keyboard   # tab 3: success
curl -X POST localhost:5001/order/mouse      # tab 3: out of stock → error span
```

### What you'll see (real output from the mouse order)

```
[inventory] trace=3e24e0bf56ef.. span=e8894e01 parent=7692f1e6  144.3ms  db.lookup_stock  {'item': 'mouse', 'quantity': 0}
[inventory] trace=3e24e0bf56ef.. span=7692f1e6 parent=84b78341  146.7ms  GET /stock/<item>
[orders   ] trace=3e24e0bf56ef.. span=84b78341 parent=51780c15  152.4ms  GET  {'http.url': '.../stock/mouse'}
[orders   ] trace=3e24e0bf56ef.. span=51780c15 parent=95e5f902  160.4ms  check_inventory
[orders   ] trace=3e24e0bf56ef.. span=95e5f902 parent=--------  162.3ms  POST /order/<item>  {'http.status_code': 409} ❌ out of stock
```

**Read it like a detective:**
- Both services print the **same trace id** (`3e24e0bf56ef..`), even though they're separate processes.
  That's context propagation.
- Inventory's `GET /stock` has parent `84b78341`, which is the *outgoing call span in orders*. The tree crosses the network.
- `POST /order` has no parent, so it's the **root span**.
- Of the 162ms total, 144ms was the DB lookup. **You just found the bottleneck.**
- Spans print bottom-up because a span is exported when it *finishes*, and children finish first.

Want to see the raw JSON that real backends receive? Run with `OTEL_RAW_CONSOLE=1 python orders.py`.

## Part 4: Exercises (do these and you understand OTel)

1. **Break propagation.** Comment out `RequestsInstrumentor().instrument()` in `orders.py` and rerun.
   Inventory now starts a *new* trace id. This is the #1 real-world tracing bug.
2. **Add a span.** Wrap a fake "send confirmation email" step in `orders.py` with its own span and a `time.sleep`.
3. **See the header.** In `inventory.py`, print `request.headers.get("traceparent")`.
   Format: `00-<trace_id>-<parent_span_id>-01`.
4. **Add a metric.** Look up `opentelemetry.metrics` and count orders with a `Counter`, split by `item`.
5. **Get the visual waterfall (needs Docker).** Install Docker Desktop, then:
   ```bash
   docker run --rm -p 16686:16686 -p 4318:4318 jaegertracing/jaeger:latest
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 python orders.py   # same for inventory
   ```
   Open http://localhost:16686 to see the trace as a timeline. **This screenshot is your LinkedIn image.**

## Part 5: Interview-ready one-liners

- *"Traces show where time went in one request; metrics show trends across all requests; logs show details."*
- *"Context propagation passes the trace id between services through the W3C `traceparent` header."*
- *"The OTel Collector decouples apps from backends: apps send OTLP to the collector, and the collector routes to Jaeger, Datadog, or wherever."*
- *"Sampling: at high traffic you don't keep 100% of traces. Head sampling decides at the start; tail sampling decides after seeing the whole trace, for example keep only errors and slow ones."*

## Part 6: Post ideas from this one demo

1. **Concept post:** "Your request is slow. Which of your 6 microservices is to blame?" Explain the 3 signals and OTel as USB-C.
2. **Build post:** "I traced a request across 2 services in 40 lines of Python." Include the waterfall screenshot and the repo link.
3. **Gotcha post:** "How a single missing line broke my distributed trace." That's exercise 1, explaining `traceparent`.

## Resources

- Official concepts (read "Observability primer" + "Traces"): https://opentelemetry.io/docs/concepts/
- Python getting started: https://opentelemetry.io/docs/languages/python/getting-started/
- W3C Trace Context spec (skim it): https://www.w3.org/TR/trace-context/
