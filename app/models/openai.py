from typing import Literal

from pydantic import BaseModel, Field


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


class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]


class ModelObject(BaseModel):
    id: str
    object: Literal["model"] = "model"
    created: int = 0
    owned_by: str = "local"


class ModelListResponse(BaseModel):
    object: Literal["list"] = "list"
    data: list[ModelObject]