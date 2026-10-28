from time import perf_counter

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.observability.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
)


class PrometheusMetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
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

        if scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        method = scope["method"]
        status_code = 500
        start_time = perf_counter()

        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=method,
        ).inc()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration = perf_counter() - start_time

            route = self._get_route(scope)

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                route=route,
                status_code=str(status_code),
            ).inc()

            HTTP_REQUEST_DURATION_SECONDS.labels(
                method=method,
                route=route,
            ).observe(duration)

            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=method,
            ).dec()

    @staticmethod
    def _get_route(scope: Scope) -> str:
        matched_route = scope.get("route")

        if matched_route is None:
            return "unmatched"

        route_path = getattr(matched_route, "path_format", None)

        if route_path is None:
            return "unmatched"

        app = scope.get("app")

        if app is None:
            return route_path

        for registered_route in app.routes:
            include_context = getattr(
                registered_route,
                "include_context",
                None,
            )

            if include_context is None:
                continue

            original_router = getattr(
                registered_route,
                "original_router",
                None,
            )

            if original_router is None:
                continue

            if matched_route in original_router.routes:
                prefix = include_context.prefix
                return prefix + route_path

        return route_path