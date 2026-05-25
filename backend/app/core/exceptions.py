import logging
from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("gpip.errors")

_FRIENDLY_HTTP_MESSAGES = {
    400: "The request could not be processed. Please check your input and try again.",
    401: "Authentication required. Please sign in again.",
    403: "You do not have permission to perform this action.",
    404: "The requested resource was not found.",
    405: "This operation is not allowed for the requested resource.",
    409: "The request conflicts with existing data.",
    422: "Validation failed. Please check the highlighted fields.",
    429: "Too many requests. Please wait a moment and try again.",
    500: "An unexpected error occurred. Please try again shortly.",
    502: "The service is temporarily unavailable. Please try again shortly.",
    503: "The service is temporarily unavailable. Please try again shortly.",
    504: "The request timed out. Please try again.",
}


def http_error(status_code: int, message: str, detail=None) -> HTTPException:
    body = {"success": False, "message": message}
    if detail is not None:
        body["detail"] = detail
    return HTTPException(status_code=status_code, detail=body)


def _friendly_message(status_code: int, detail: Any) -> str:
    if isinstance(detail, dict) and detail.get("message"):
        return str(detail["message"])
    if isinstance(detail, str) and detail.strip():
        return detail
    return _FRIENDLY_HTTP_MESSAGES.get(
        status_code,
        "The request could not be completed.",
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    logger.warning(
        "Validation error on %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    errors = [
        {
            "field": ".".join(str(loc) for loc in err.get("loc", [])),
            "message": err.get("msg", "Invalid value"),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": _FRIENDLY_HTTP_MESSAGES[422],
            "detail": errors,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code >= 500:
        logger.error(
            "HTTP %s on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
    elif exc.status_code >= 400:
        logger.info(
            "HTTP %s on %s %s: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )

    if isinstance(exc.detail, dict) and "message" in exc.detail:
        content = dict(exc.detail)
        content.setdefault("success", False)
        return JSONResponse(status_code=exc.status_code, content=content)

    message = _friendly_message(exc.status_code, exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": message,
            "detail": exc.detail if exc.detail != message else None,
        },
    )
