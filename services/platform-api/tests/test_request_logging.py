import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.request_logging import RequestLoggingMiddleware


def create_test_app() -> FastAPI:
    app = FastAPI()

    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/test")
    def test_endpoint():
        return {"message": "ok"}

    return app


def test_request_logging_records_success(caplog):
    app = create_test_app()

    with caplog.at_level(logging.INFO, logger="platformforge.http"):
        with TestClient(app) as client:
            response = client.get("/test")

    assert response.status_code == 200

    assert any(
        "HTTP request completed: GET /test status=200" in record.getMessage()
        for record in caplog.records
    )


def test_request_logging_records_http_error(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/missing-resource")
    def missing_resource():
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Not found")

    with caplog.at_level(logging.INFO, logger="platformforge.http"):
        with TestClient(app) as client:
            response = client.get("/missing-resource")

    assert response.status_code == 404

    assert any(
        "status=404" in record.getMessage()
        for record in caplog.records
    )


def test_request_logging_records_unhandled_exception(caplog):
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/failure")
    def failing_endpoint():
        raise RuntimeError("Unexpected failure")

    with caplog.at_level(logging.ERROR, logger="platformforge.http"):
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/failure")

    assert response.status_code == 500

    assert any(
        record.levelno == logging.ERROR
        and "HTTP request failed" in record.getMessage()
        for record in caplog.records
    )