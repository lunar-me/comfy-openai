from fastapi import HTTPException

from app.comfy.client import ComfyError
from app.comfy.executor import ExecutionTimeoutError
from app.comfy.workflow import (
    InvalidSizeError,
    InvalidVideoParamsError,
    ModelNotFoundError,
)


def comfy_error_to_http(exc: Exception) -> HTTPException:
    """Map a ComfyUI/domain exception to an OpenAI-style HTTP error response."""
    if isinstance(exc, ModelNotFoundError):
        return HTTPException(
            status_code=404,
            detail={
                "message": str(exc),
                "type": "invalid_request_error",
                "param": "model",
                "code": "model_not_found",
            },
        )
    if isinstance(exc, InvalidSizeError):
        return HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "type": "invalid_request_error",
                "param": "size",
                "code": "invalid_size",
            },
        )
    if isinstance(exc, InvalidVideoParamsError):
        return HTTPException(
            status_code=400,
            detail={
                "message": str(exc),
                "type": "invalid_request_error",
                "param": exc.param,
                "code": "invalid_video_params",
            },
        )
    if isinstance(exc, ExecutionTimeoutError):
        return HTTPException(
            status_code=504,
            detail={
                "message": str(exc),
                "type": "server_error",
                "param": None,
                "code": "comfy_timeout",
            },
        )
    if isinstance(exc, ComfyError):
        return HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "type": "server_error",
                "param": None,
                "code": "comfy_execution_error",
            },
        )
    return HTTPException(
        status_code=500,
        detail={
            "message": str(exc),
            "type": "server_error",
            "param": None,
            "code": "internal_error",
        },
    )
