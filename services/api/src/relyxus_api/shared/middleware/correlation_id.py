"""Binds a correlation ID to each request, echoes it in the response and logs the request.

Written as pure ASGI middleware so the ID is set before routing, validation and error
handling run. Only method, path, status and duration are logged; never query strings,
headers or bodies, which can carry tokens or customer data.
"""

import logging
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from relyxus_api.shared.constants import CORRELATION_HEADER
from relyxus_api.shared.observability.correlation import bind_correlation_id

logger = logging.getLogger(__name__)
_MILLISECONDS_PER_SECOND = 1000


class CorrelationIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = bind_correlation_id(Headers(scope=scope).get(CORRELATION_HEADER))
        started_at = time.perf_counter()
        response_status: list[int] = []

        async def send_with_correlation_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                if CORRELATION_HEADER not in headers:
                    headers.append(CORRELATION_HEADER, correlation_id)
                response_status.append(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        finally:
            logger.info(
                "request completed",
                extra={
                    "http_method": scope["method"],
                    "http_path": scope["path"],
                    "http_status": response_status[0] if response_status else None,
                    "duration_ms": round(
                        (time.perf_counter() - started_at) * _MILLISECONDS_PER_SECOND, 1
                    ),
                },
            )
