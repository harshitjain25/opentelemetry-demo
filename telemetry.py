"""
Shared OpenTelemetry setup used by both services.

The 3 building blocks you always see in OTel setup code:
  1. Resource       -> "who am I?"  (service name, version, env)
  2. TracerProvider -> the factory that creates tracers/spans
  3. Exporter       -> "where do spans go?" (console, Jaeger, a vendor...)
"""
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)


class PrettyConsoleExporter(SpanExporter):
    """Prints each finished span as one readable line (instead of a JSON wall)."""

    def export(self, spans):
        for s in spans:
            ctx = s.get_span_context()
            parent = format(s.parent.span_id, "016x") if s.parent else "-" * 16
            ms = (s.end_time - s.start_time) / 1e6
            svc = s.resource.attributes.get("service.name")
            # Hide the noisy auto-added network attributes; keep status + your own ones.
            attrs = {k: v for k, v in (s.attributes or {}).items()
                     if k in ("http.status_code", "http.url")
                     or not k.startswith(("http.", "net.", "user_agent"))}
            status = " ❌ " + (s.status.description or "") if not s.status.is_ok else ""
            print(
                f"[{svc:<9}] trace={format(ctx.trace_id, '032x')[:12]}.. "
                f"span={format(ctx.span_id, '016x')[:8]} parent={parent[:8]} "
                f"{ms:7.1f}ms  {s.name}  {attrs or ''}{status}",
                flush=True,
            )
        return SpanExportResult.SUCCESS


def setup_tracing(service_name: str):
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        # Send to a real backend (Jaeger, Grafana Tempo, Honeycomb...) over OTLP.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    elif os.getenv("OTEL_RAW_CONSOLE"):
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(SimpleSpanProcessor(PrettyConsoleExporter()))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
