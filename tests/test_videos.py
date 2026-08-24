import base64

from fastapi.testclient import TestClient

from app.api.videos import get_video_executor, get_video_storage
from app.comfy.executor import ExecutionResult, OutputVideo
from app.main import app


class FakeExecutor:
    """Stub executor that returns a single fake video."""

    def __init__(self):
        self.client = FakeComfyClient()

    async def execute(self, workflow: dict) -> ExecutionResult:
        return ExecutionResult(videos=[OutputVideo(filename="fake.mp4", format="mp4")])


class FakeComfyClient:
    """Stub ComfyUI client returning fixed video bytes."""

    async def get_video(self, filename, subfolder="", type="output") -> bytes:
        return b"fake-video-bytes"


class FakeStorage:
    def __init__(self):
        self.saved: list[bytes] = []

    def save(self, data: bytes, extension: str = "mp4") -> str:
        self.saved.append(data)
        return f"http://localhost:8000/videos/fake.{extension}"


client = TestClient(app)


def test_video_generation_returns_url_and_b64():
    fake_storage = FakeStorage()
    app.dependency_overrides[get_video_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_video_storage] = lambda: fake_storage

    try:
        response = client.post(
            "/v1/videos/generations",
            json={
                "model": "minimax-h3-t2v",
                "prompt": "a test video",
                "aspect_ratio": "16:9 (Widescreen)",
                "megapixels": 0.4,
                "duration": 5,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert "created" in payload
    assert len(payload["data"]) == 1

    item = payload["data"][0]
    assert item["url"] == "http://localhost:8000/videos/fake.mp4"
    assert item["b64_json"] == base64.b64encode(b"fake-video-bytes").decode("ascii")


def test_video_generation_accepts_duration_string():
    fake_storage = FakeStorage()
    app.dependency_overrides[get_video_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_video_storage] = lambda: fake_storage

    try:
        response = client.post(
            "/v1/videos/generations",
            json={
                "model": "minimax-h3-t2v",
                "prompt": "a test video",
                "duration": "10s",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert len(response.json()["data"]) == 1


def test_video_generation_unknown_model_returns_404():
    app.dependency_overrides[get_video_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_video_storage] = lambda: FakeStorage()

    try:
        response = client.post(
            "/v1/videos/generations",
            json={
                "model": "does-not-exist",
                "prompt": "a test video",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "model_not_found"


def test_video_generation_rejects_image_model():
    app.dependency_overrides[get_video_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_video_storage] = lambda: FakeStorage()

    try:
        response = client.post(
            "/v1/videos/generations",
            json={
                "model": "flux",
                "prompt": "a test video",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "model_not_found"


def test_video_generation_rejects_invalid_aspect_ratio():
    app.dependency_overrides[get_video_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_video_storage] = lambda: FakeStorage()

    try:
        response = client.post(
            "/v1/videos/generations",
            json={
                "model": "minimax-h3-t2v",
                "prompt": "a test video",
                "aspect_ratio": "5:4 (Bogus)",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_video_params"
    assert detail["param"] == "aspect_ratio"


def test_video_generation_rejects_invalid_megapixels():
    app.dependency_overrides[get_video_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_video_storage] = lambda: FakeStorage()

    try:
        response = client.post(
            "/v1/videos/generations",
            json={
                "model": "minimax-h3-t2v",
                "prompt": "a test video",
                "megapixels": 3.5,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_video_params"
    assert detail["param"] == "megapixels"
