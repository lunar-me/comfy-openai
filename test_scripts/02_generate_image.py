#!/usr/bin/env python3
"""Minimal test: POST /v1/images/generations — text-to-image.

Run the API server first (python main.py), then:
    python test_scripts/02_generate_image.py

The generated image is saved as ``response_image.png`` (or ``.jpg``, depending
on the detected format) in the current directory.
"""

import base64
import os

import httpx

from _env import api_base_url, load_env

load_env()

BASE_URL = api_base_url()
API_KEY = os.environ.get("API_KEY", "local-key")
MODEL = os.environ.get("MODEL", "flux")
OUTPUT_IMAGE = os.environ.get("OUTPUT_IMAGE", "response_image")


def detect_extension(data: bytes) -> str:
    """Detect image format from magic bytes: PNG or JPEG (default PNG)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return ".png"


def main() -> None:
    response = httpx.post(
        f"{BASE_URL}/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "prompt": "A suburban house with a swimming pool at dusk",
            "size": "1024x1024",
            "n": 1,
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