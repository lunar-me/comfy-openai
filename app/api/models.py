from fastapi import APIRouter

from app.comfy.workflow import load_models
from app.models.openai import ModelListResponse, ModelObject

router = APIRouter()


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models() -> ModelListResponse:
    data = [
        ModelObject(
            id=model_id,
            owned_by=entry.get("owned_by", "local"),
        )
        for model_id, entry in load_models().items()
    ]
    return ModelListResponse(data=data)
