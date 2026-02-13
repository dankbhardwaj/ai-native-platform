from fastapi import FastAPI
from prometheus_client import Counter, generate_latest
from starlette.responses import Response

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

app = FastAPI()

# Prometheus metric
REQUEST_COUNT = Counter("app_requests_total", "Total app requests")

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(
    endpoint="otel-collector.tracing.svc.cluster.local:4317",
    insecure=True,
)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

FastAPIInstrumentor.instrument_app(app)

@app.get("/")
def read_root():
    REQUEST_COUNT.inc()
    with tracer.start_as_current_span("root-handler"):
        return {"message": "AI Native Platform API Running with Tracing"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")
