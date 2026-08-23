#!/usr/bin/env python3
"""Minimal test: POST /v1/images/edits — image edit (img2img).

Run the API server first (python main.py), then:
    python test_scripts/03_edit_image.py [path_to_input_image]

Example:
    python test_scripts/03_edit_image.py input.png

The generated image is saved as response_image.png (or .jpg, depending on the
detected format) in the current directory.
"""

import base64
import os
import sys

import httpx

from _env import load_env

load_env()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000/v1")
API_KEY = os.environ.get("API_KEY", "local-key")
MODEL = os.environ.get("MODEL", "flux-edit")
INPUT_IMAGE = sys.argv[1] if len(sys.argv) > 1 else "house_and_pool.png"
OUTPUT_IMAGE = os.environ.get("OUTPUT_IMAGE", "response_image")


def detect_extension(data: bytes) -> str:
    """Detect image format from magic bytes: PNG or JPEG (default PNG)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return ".png"


def main() -> None:
    with open(INPUT_IMAGE, "rb") as f:
        image_bytes = f.read()

    response = httpx.post(
        f"{BASE_URL}/images/edits",
        headers={"Authorization": f"Bearer {API_KEY}"},
        data={
            "model": MODEL,
            "prompt": "Add a realistic flamingo floating in the swimming pool",
            "n": 1,
        },
        files={
            "image": (os.path.basename(INPUT_IMAGE), image_bytes, "image/png"),
        },
        timeout=300.0,
    )
    response.raise_for_status()
    data = response.json()
    item = data["data"][0]

    # Prefer b64_json (raw bytes); fall back to downloading the URL.
    if item.get("b64_json"):
        image_bytes = base64.b64decode(item["b64_json"])
    else:
        image_bytes = httpx.get(item["url"]).content

    extension = detect_extension(image_bytes)
    out_path = f"{OUTPUT_IMAGE}{extension}"
    with open(out_path, "wb") as f:
        f.write(image_bytes)

    print(f"OK - created={data['created']}")
    print(f"url={item['url']}")
    print(f"b64_json len={len(item.get('b64_json') or '')}")
    print(f"saved={out_path}")


if __name__ == "__main__":
    main()