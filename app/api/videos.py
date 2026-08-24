import base64
import time

from fastapi import APIRouter, Depends

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
