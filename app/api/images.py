import base64
import time

from fastapi import APIRouter, Depends, HTTPException

from app.comfy.client import ComfyClient, ComfyError
from app.comfy.executor import ComfyExecutor, ExecutionTimeoutError
from app.comfy.workflow import (
    InvalidSizeError,
    ModelNotFoundError,
    get_adapter,
    parse_size,
)
from app.config import settings
from app.models.openai import (
    ImageData,
    ImageGenerationRequest,
    ImageGenerationResponse,
)
from app.storage.images import ImageStorage

router = APIRouter()


def get_comfy() -> ComfyClient:
    return ComfyClient(settings.comfy_url)


def get_executor() -> ComfyExecutor:
    return ComfyExecutor(ComfyClient(settings.comfy_url))


def get_storage() -> ImageStorage:
    return ImageStorage()


def _comfy_error_to_http(exc: Exception) -> HTTPException:
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


@router.post("/v1/images/generations", response_model=ImageGenerationResponse)
async def generate_images(
    request: ImageGenerationRequest,
    executor: ComfyExecutor = Depends(get_executor),
    storage: ImageStorage = Depends(get_storage),
):
    try:
        adapter, _model_meta = get_adapter(request.model)
        width, height = parse_size(request.size)

        workflow = adapter.build(
            prompt=request.prompt,
            width=width,
            height=height,
            seed=request.seed,
            n=request.n,
            negative_prompt=request.negative_prompt,
            steps=request.steps,
            cfg=request.cfg,
        )

        result = await executor.execute(workflow)

        images: list[ImageData] = []
        for output_image in result.images:
            data = await executor.client.get_image(
                output_image.filename,
                output_image.subfolder,
                output_image.type,
            )

            if request.response_format == "b64_json":
                images.append(
                    ImageData(
                        b64_json=base64.b64encode(data).decode("ascii"),
                    )
                )
            else:
                url = storage.save(data)
                images.append(ImageData(url=url))

        return ImageGenerationResponse(
            created=int(time.time()),
            data=images,
        )
    except (ModelNotFoundError, InvalidSizeError, ExecutionTimeoutError, ComfyError) as exc:
        raise _comfy_error_to_http(exc) from exc
