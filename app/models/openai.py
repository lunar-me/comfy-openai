from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ImageGenerationRequest(BaseModel):
    model: str
    prompt: str
    n: int = Field(default=1, ge=1, le=4)
    size: str = "1024x1024"
    response_format: Literal["url", "b64_json"] = "url"
    seed: int | None = None
    # Optional advanced controls mapped to workflow nodes
    negative_prompt: str | None = None
    steps: int | None = None
    cfg: float | None = None


class ImageEditRequest(BaseModel):
    """OpenAI-compatible images.edit request.

    The image and mask are uploaded as multipart files. The mask is
    optional — ComfyUI img2img workflows typically only need the image.
    """
    model: str
    prompt: str
    n: int = Field(default=1, ge=1, le=4)
    size: str | None = None
    response_format: Literal["url", "b64_json"] = "url"
    seed: int | None = None
    negative_prompt: str | None = None
    steps: int | None = None
    cfg: float | None = None


class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]


class VideoGenerationRequest(BaseModel):
    """OpenAI-compatible videos.generate request.

    The MiniMax H3 text-to-video workflow is driven by a text prompt, an
    aspect ratio + megapixels pair (the ResolutionSelector node), and a
    duration in seconds (1-15). `duration` also accepts OpenAI-style strings
    like "5s" / "10s".
    """

    model: str
    prompt: str
    aspect_ratio: str = "16:9 (Widescreen)"
    megapixels: float = Field(default=0.4, gt=0)
    duration: float = Field(default=5, ge=1, le=15)
    n: int = Field(default=1, ge=1, le=4)
    response_format: Literal["url", "b64_json"] = "url"
    seed: int | None = None

    @field_validator("duration", mode="before")
    @classmethod
    def _parse_duration(cls, value):
        """Accept a float (seconds) or an OpenAI-style '5s' string."""
        if isinstance(value, str):
            text = value.strip().lower()
            if text.endswith("s"):
                text = text[:-1]
            return float(text)
        return value


class VideoData(BaseModel):
    url: str | None = None
    b64_json: str | None = None


class VideoGenerationResponse(BaseModel):
    created: int
    data: list[VideoData]


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "local"


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]