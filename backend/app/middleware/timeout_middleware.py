"""Request timeout protection for long-running API calls."""

import asyncio
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("gpip.timeout")

DEFAULT_TIMEOUT_SECONDS = 120


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        super().__init__(app)
        self.timeout_seconds = max(30, int(timeout_seconds))

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/api/health", "/", "/api/health/"):
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Request timeout (%ss) %s %s",
                self.timeout_seconds,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=504,
                content={
                    "success": False,
                    "message": "Request timed out. Please try again or narrow your query.",
                    "detail": None,
                },
            )
