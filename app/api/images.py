import base64
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.api.errors import comfy_error_to_http
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
    ImageEditRequest,
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

            url = storage.save(data)
            images.append(
                ImageData(
                    url=url,
                    b64_json=base64.b64encode(data).decode("ascii"),
                )
            )

        return ImageGenerationResponse(
            created=int(time.time()),
            data=images,
        )
    except (ModelNotFoundError, InvalidSizeError, ExecutionTimeoutError, ComfyError) as exc:
        raise comfy_error_to_http(exc) from exc


@router.post("/v1/images/edits", response_model=ImageGenerationResponse)
async def edit_images(
    model: str = Form(...),
    prompt: str = Form(...),
    image: UploadFile = File(...),
    mask: UploadFile | None = File(default=None),
    n: int = Form(default=1),
    size: str | None = Form(default=None),
    response_format: str = Form(default="url"),
    seed: int | None = Form(default=None),
    negative_prompt: str | None = Form(default=None),
    steps: int | None = Form(default=None),
    cfg: float | None = Form(default=None),
    executor: ComfyExecutor = Depends(get_executor),
    storage: ImageStorage = Depends(get_storage),
):
    """OpenAI-compatible images.edit endpoint (multipart form).

    Accepts an input image (and optional mask) plus a prompt, uploads the
    image to ComfyUI, and runs the model's img2img workflow.
    """
    try:
        adapter, _model_meta = get_adapter(model)

        # Persist the uploaded image to ComfyUI's input dir and reference it
        # by the returned filename in the LoadImage node.
        image_bytes = await image.read()
        upload = await executor.client.upload_image(
            data=image_bytes,
            filename=image.filename or "input.png",
        )
        input_image = upload.get("name", image.filename or "input.png")

        # Optional size -> width/height (the img2img workflow derives size
        # from the image when size is omitted).
        width = height = None
        if size:
            width, height = parse_size(size)

        request = ImageEditRequest(
            model=model,
            prompt=prompt,
            n=n,
            size=size,
            response_format=response_format,  # type: ignore[arg-type]
            seed=seed,
            negative_prompt=negative_prompt,
            steps=steps,
            cfg=cfg,
        )

        workflow = adapter.build(
            prompt=request.prompt,
            width=width,
            height=height,
            seed=request.seed,
            n=request.n,
            negative_prompt=request.negative_prompt,
            steps=request.steps,
            cfg=request.cfg,
            input_image=input_image,
        )

        result = await executor.execute(workflow)

        images: list[ImageData] = []
        for output_image in result.images:
            data = await executor.client.get_image(
                output_image.filename,
                output_image.subfolder,
                output_image.type,
            )

            url = storage.save(data)
            images.append(
                ImageData(
                    url=url,
                    b64_json=base64.b64encode(data).decode("ascii"),
                )
            )

        return ImageGenerationResponse(
            created=int(time.time()),
            data=images,
        )
    except (ModelNotFoundError, InvalidSizeError, ExecutionTimeoutError, ComfyError) as exc:
        raise comfy_error_to_http(exc) from exc
