"""Request timeout protection for long-running API calls."""

import asyncio
import logging
import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("gpip.timeout")

DEFAULT_TIMEOUT_SECONDS = 120


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        super().__init__(app)
        self.timeout_seconds = max(30, int(timeout_seconds))

    def _timeout_for_path(self, path: str) -> int:
        normalized = path.rstrip("/")
        if normalized == "/api/ocr/upload":
            ocr_timeout = int(os.getenv("OCR_REQUEST_TIMEOUT_SECONDS", "300"))
            return max(self.timeout_seconds, min(ocr_timeout, 600))
        if normalized == "/api/upload-files":
            # Receive-only; processing runs in background after job_id is returned.
            return max(self.timeout_seconds, 300)
        return self.timeout_seconds

    async def dispatch(self, request: Request, call_next):
        if request.url.path.rstrip("/") in (
            "/api/health",
            "/api/ocr/health",
            "/",
        ) or request.url.path.rstrip("/").startswith("/api/upload-jobs/"):
            return await call_next(request)

        timeout = self._timeout_for_path(request.url.path)
        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Request timeout (%ss) %s %s",
                timeout,
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
