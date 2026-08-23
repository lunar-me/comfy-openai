import base64

from fastapi.testclient import TestClient

from app.api.images import get_executor, get_storage
from app.comfy.executor import ExecutionResult, OutputImage
from app.main import app


class FakeExecutor:
    """Stub executor that returns a single fake image."""

    def __init__(self):
        self.client = FakeComfyClient()

    async def execute(self, workflow: dict) -> ExecutionResult:
        return ExecutionResult(images=[OutputImage(filename="fake.png")])


class FakeComfyClient:
    """Stub ComfyUI client returning fixed image bytes."""

    async def get_image(self, filename, subfolder="", type="output") -> bytes:
        return b"\x89PNG-fake-image-bytes"


class FakeStorage:
    def __init__(self):
        self.saved: list[bytes] = []

    def save(self, data: bytes, extension: str = "png") -> str:
        self.saved.append(data)
        return f"http://localhost:8000/images/fake.{extension}"


client = TestClient(app)


def test_generation_returns_both_url_and_b64_json():
    fake_storage = FakeStorage()
    app.dependency_overrides[get_executor] = lambda: FakeExecutor()
    app.dependency_overrides[get_storage] = lambda: fake_storage

    try:
        response = client.post(
            "/v1/images/generations",
            json={
                "model": "flux",
                "prompt": "a test image",
                "size": "1024x1024",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert "created" in payload
    assert len(payload["data"]) == 1

    item = payload["data"][0]
    assert item["url"] == "http://localhost:8000/images/fake.png"
    assert item["b64_json"] == base64.b64encode(b"\x89PNG-fake-image-bytes").decode("ascii")