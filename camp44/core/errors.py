import traceback

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    traceback.print_exc()

    span = trace.get_current_span()
    if span and span.is_recording():
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, description=str(exc)))

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal Server Error",
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
            }
        },
    )
