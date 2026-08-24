from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.images import router as images_router
from app.api.models import router as models_router
from app.api.videos import router as videos_router
from app.config import settings
from app.storage.images import ImageStorage
from app.storage.videos import VideoStorage

app = FastAPI(title="ComfyUI OpenAI-compatible API")

app.include_router(models_router)
app.include_router(images_router)
app.include_router(videos_router)

# Serve saved images from the output directory at /images/<file>
storage = ImageStorage()
app.mount(
    "/images",
    StaticFiles(directory=str(storage.output_dir)),
    name="images",
)

# Serve saved videos from the output directory at /videos/<file>
video_storage = VideoStorage()
app.mount(
    "/videos",
    StaticFiles(directory=str(video_storage.output_dir)),
    name="videos",
)
