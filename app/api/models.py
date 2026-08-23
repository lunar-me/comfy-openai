from fastapi import APIRouter

from app.comfy.workflow import MODELS
from app.models.openai import ModelListResponse, ModelObject

router = APIRouter()


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    data = [
        ModelObject(
            id=model_id,
            owned_by=entry.get("owned_by", "local"),
        )
        for model_id, entry in MODELS.items()
    ]
    return ModelListResponse(data=data)