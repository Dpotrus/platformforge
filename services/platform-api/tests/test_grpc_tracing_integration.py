from concurrent import futures

import grpc

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind
from opentelemetry.instrumentation.grpc import server_interceptor
from platformforge.v1 import applications_pb2, applications_pb2_grpc
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


class TestApplicationServicer(applications_pb2_grpc.ApplicationServiceServicer):

    def ListApplications(self, request, context):
        return applications_pb2.ListApplicationsResponse()


def test_grpc_request_creates_server_span() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        interceptors=[
            server_interceptor(tracer_provider=provider),
        ],
    )

    applications_pb2_grpc.add_ApplicationServiceServicer_to_server(
        TestApplicationServicer(),
        server,
    )

    port = server.add_insecure_port("127.0.0.1:0")
    assert port != 0

    try:
        server.start()

        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            grpc.channel_ready_future(channel).result(timeout=5)

            stub = applications_pb2_grpc.ApplicationServiceStub(
                channel
            )

            response = stub.ListApplications(
                applications_pb2.ListApplicationsRequest(),
                timeout=5,
            )

        assert isinstance(
            response,
            applications_pb2.ListApplicationsResponse,
        )

        spans = exporter.get_finished_spans()

        server_spans = [
            span
            for span in spans
            if span.kind == SpanKind.SERVER
        ]

        assert len(server_spans) == 1

        assert "ListApplications" in server_spans[0].name

    finally:
        server.stop(grace=0).wait(timeout=5)
        provider.shutdown()


def test_grpc_server_span_is_parent_of_application_span() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    tracer = provider.get_tracer("platformforge.grpc.test")

    class TracedApplicationServicer(
        applications_pb2_grpc.ApplicationServiceServicer
    ):
        def ListApplications(self, request, context):
            with tracer.start_as_current_span(
                    "platformforge.application.list"
            ):
                return applications_pb2.ListApplicationsResponse()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        interceptors=[
            server_interceptor(tracer_provider=provider),
        ],
    )

    applications_pb2_grpc.add_ApplicationServiceServicer_to_server(
        TracedApplicationServicer(),
        server,
    )

    port = server.add_insecure_port("127.0.0.1:0")
    assert port != 0

    try:
        server.start()

        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            grpc.channel_ready_future(channel).result(timeout=5)

            stub = applications_pb2_grpc.ApplicationServiceStub(
                channel
            )

            stub.ListApplications(
                applications_pb2.ListApplicationsRequest(),
                timeout=5,
            )

        spans = exporter.get_finished_spans()

        server_span = next(
            span for span in spans
            if span.kind == SpanKind.SERVER
        )

        application_span = next(
            span for span in spans
            if span.name == "platformforge.application.list"
        )

        assert application_span.context.trace_id == (
            server_span.context.trace_id
        )

        assert application_span.parent.span_id == (
            server_span.context.span_id
        )

    finally:
        server.stop(grace=0).wait(timeout=5)
        provider.shutdown()



def test_grpc_server_span_is_parent_of_sqlalchemy_span() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    instrumentor = SQLAlchemyInstrumentor()
    instrumentor.instrument(
        engine=engine,
        tracer_provider=provider,
    )

    class DatabaseApplicationServicer(
        applications_pb2_grpc.ApplicationServiceServicer
    ):
        def ListApplications(self, request, context):
            with Session(engine) as session:
                session.execute(text("SELECT 1")).scalar_one()

            return applications_pb2.ListApplicationsResponse()

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=2),
        interceptors=[
            server_interceptor(tracer_provider=provider),
        ],
    )

    applications_pb2_grpc.add_ApplicationServiceServicer_to_server(
        DatabaseApplicationServicer(),
        server,
    )

    port = server.add_insecure_port("127.0.0.1:0")
    assert port != 0

    try:
        server.start()

        with grpc.insecure_channel(f"127.0.0.1:{port}") as channel:
            grpc.channel_ready_future(channel).result(timeout=5)

            stub = applications_pb2_grpc.ApplicationServiceStub(channel)

            stub.ListApplications(
                applications_pb2.ListApplicationsRequest(),
                timeout=5,
            )

        spans = exporter.get_finished_spans()

        server_span = next(
            span for span in spans
            if span.kind == SpanKind.SERVER
        )

        database_spans = [
            span for span in spans
            if span.kind == SpanKind.CLIENT
               and "SELECT" in span.name.upper()
        ]

        assert database_spans, "Expected a SQLAlchemy SELECT span"

        database_span = database_spans[0]

        assert database_span.context.trace_id == (
            server_span.context.trace_id
        )

        assert database_span.parent is not None
        assert database_span.parent.span_id == (
            server_span.context.span_id
        )

    finally:
        server.stop(grace=0).wait(timeout=5)
        instrumentor.uninstrument()
        engine.dispose()
        provider.shutdown()
