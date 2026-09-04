import base64
import time

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.errors import comfy_error_to_http
from app.comfy.client import ComfyClient, ComfyError
from app.comfy.executor import ComfyExecutor, ExecutionTimeoutError
from app.comfy.workflow import (
    InvalidVideoParamsError,
    ModelNotFoundError,
    get_video_adapter,
    validate_video_params,
)
from app.config import settings
from app.models.openai import (
    VideoData,
    VideoGenerationRequest,
    VideoGenerationResponse,
)
from app.storage.videos import VideoStorage

router = APIRouter()


def get_video_executor() -> ComfyExecutor:
    # Video generation is slow (often minutes), so allow a long render window.
    return ComfyExecutor(ComfyClient(settings.comfy_url), timeout=1800.0)


def get_video_storage() -> VideoStorage:
    return VideoStorage()


@router.post("/v1/videos/generations", response_model=VideoGenerationResponse)
async def generate_videos(
    request: VideoGenerationRequest,
    executor: ComfyExecutor = Depends(get_video_executor),
    storage: VideoStorage = Depends(get_video_storage),
):
    """OpenAI-compatible videos.generate endpoint (synchronous).

    Runs the model's text-to-video workflow once per requested video and returns
    each rendered video as a URL and/or base64 payload.
    """
    try:
        adapter, model_meta = get_video_adapter(request.model)
        validate_video_params(request.aspect_ratio, request.megapixels, model_meta)

        videos: list[VideoData] = []
        for _ in range(request.n):
            workflow = adapter.build(
                prompt=request.prompt,
                aspect_ratio=request.aspect_ratio,
                megapixels=request.megapixels,
                duration=request.duration,
                seed=request.seed,
            )

            result = await executor.execute(workflow)

            for output_video in result.videos:
                data = await executor.client.get_video(
                    output_video.filename,
                    output_video.subfolder,
                    output_video.type,
                )

                url = storage.save(data, extension=output_video.format or "mp4")
                videos.append(
                    VideoData(
                        url=url,
                        b64_json=base64.b64encode(data).decode("ascii"),
                    )
                )

        return VideoGenerationResponse(
            created=int(time.time()),
            data=videos,
        )
    except (ModelNotFoundError, InvalidVideoParamsError, ExecutionTimeoutError, ComfyError) as exc:
        raise comfy_error_to_http(exc) from exc


@router.post("/v1/videos/edits", response_model=VideoGenerationResponse)
async def edit_videos(
    model: str = Form(...),
    prompt: str = Form(...),
    image: UploadFile = File(...),
    megapixels: float = Form(default=0.4),
    duration: float = Form(default=5),
    n: int = Form(default=1),
    response_format: str = Form(default="url"),
    seed: int | None = Form(default=None),
    executor: ComfyExecutor = Depends(get_video_executor),
    storage: VideoStorage = Depends(get_video_storage),
):
    """OpenAI-compatible image-to-video endpoint (multipart form).

    Accepts an input image plus a text prompt, uploads the image to ComfyUI, and
    runs the model's image-to-video workflow. Image-to-video takes a target
    megapixels value but no aspect_ratio (the workflow derives the resolution
    from the input image).
    """
    try:
        adapter, model_meta = get_video_adapter(model)
        validate_video_params(None, megapixels, model_meta)

        # Persist the uploaded image to ComfyUI's input dir and reference it by
        # the returned filename in the LoadImage node.
        image_bytes = await image.read()
        upload = await executor.client.upload_image(
            data=image_bytes,
            filename=image.filename or "input.png",
        )
        input_image = upload.get("name", image.filename or "input.png")

        videos: list[VideoData] = []
        for _ in range(n):
            workflow = adapter.build(
                prompt=prompt,
                megapixels=megapixels,
                duration=duration,
                seed=seed,
                input_image=input_image,
            )

            result = await executor.execute(workflow)

            for output_video in result.videos:
                data = await executor.client.get_video(
                    output_video.filename,
                    output_video.subfolder,
                    output_video.type,
                )

                url = storage.save(data, extension=output_video.format or "mp4")
                videos.append(
                    VideoData(
                        url=url,
                        b64_json=base64.b64encode(data).decode("ascii"),
                    )
                )

        return VideoGenerationResponse(
            created=int(time.time()),
            data=videos,
        )
    except (ModelNotFoundError, InvalidVideoParamsError, ExecutionTimeoutError, ComfyError) as exc:
        raise comfy_error_to_http(exc) from exc
