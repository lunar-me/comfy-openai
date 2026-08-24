import secrets
from pathlib import Path

from app.config import settings


class VideoStorage:
    """Saves generated videos to a local output directory and builds their URLs."""

    def __init__(self, output_dir: str | None = None, base_url: str | None = None):
        self.output_dir = Path(output_dir or settings.output_dir)
        self.base_url = (base_url or settings.base_url).rstrip("/")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, extension: str = "mp4") -> str:
        """Save video bytes and return a URL path under /videos/<name>."""
        name = f"{secrets.token_hex(8)}.{extension}"
        path = self.output_dir / name
        path.write_bytes(data)
        return f"{self.base_url}/videos/{name}"
