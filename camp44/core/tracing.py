from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
import atexit
import os

# Global reference to tracer components for proper cleanup
_tracer_provider = None
_span_processor = None


def setup_tracer():
    """Configure the OpenTelemetry tracer."""
    global _tracer_provider, _span_processor
    
    # Skip tracing setup in test environment
    if os.environ.get("TESTING") == "1":
        return
        
    resource = Resource.create({"service.name": "camp44"})
    _tracer_provider = TracerProvider(resource=resource)
    _span_processor = BatchSpanProcessor(ConsoleSpanExporter())
    _tracer_provider.add_span_processor(_span_processor)
    trace.set_tracer_provider(_tracer_provider)
    
    # Register shutdown at exit
    atexit.register(shutdown_tracer)


def shutdown_tracer():
    """Properly shut down the tracer to avoid file closure issues."""
    global _tracer_provider, _span_processor
    
    if _span_processor:
        # Force flush any pending spans
        _span_processor.force_flush()
        # Shutdown the processor
        _span_processor.shutdown()
        _span_processor = None
        
    if _tracer_provider:
        # Shutdown the provider
        _tracer_provider.shutdown()
        _tracer_provider = None
