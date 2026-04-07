"""Request ID middleware for tracing requests across the system.

Generates a UUID4 request_id for each incoming request, binds it to the
structlog context, and returns it in the X-Request-ID response header.
Reference: ARCHITECTURE.md Section 10.1 (Logging).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

logger = structlog.get_logger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request_id into every request lifecycle.

    If the client sends an X-Request-ID header, it is reused (passthrough).
    Otherwise, a new UUID4 is generated. The ID is:
      - Bound to the structlog context (all log lines include it)
      - Stored on request.state.request_id
      - Returned in the X-Request-ID response header
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process the request with request ID injection.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response with X-Request-ID header added.
        """
        # Reuse client-provided ID or generate a new one
        request_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())

        # Make the ID available to route handlers
        request.state.request_id = request_id

        # Bind to structlog context so every log line includes it
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response = await call_next(request)

        # Echo the request ID back to the client
        response.headers[_REQUEST_ID_HEADER] = request_id

        return response
