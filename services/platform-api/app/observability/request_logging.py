import logging
import time

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("platformforge.http")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(
            self,
            scope: Scope,
            receive: Receive,
            send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        path = scope["path"]
        start_time = time.perf_counter()

        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.exception(
                "HTTP request failed: %s %s status=%s duration_ms=%.2f",
                method,
                path,
                status_code,
                duration_ms,
            )

            raise
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "HTTP request completed: %s %s status=%s duration_ms=%.2f",
                method,
                path,
                status_code,
                duration_ms,
            )