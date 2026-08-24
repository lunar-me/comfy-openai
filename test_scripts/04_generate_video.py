#!/usr/bin/env python3
"""Minimal test: POST /v1/videos/generations — text-to-video.

Run the API server first (python main.py), then:
    python test_scripts/04_generate_video.py

The generated video is saved as ``response_video.mp4`` in the current directory.
"""

import base64
import os

import httpx

from _env import load_env

load_env()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000/v1")
API_KEY = os.environ.get("API_KEY", "local-key")
MODEL = os.environ.get("MODEL", "minimax-h3-t2v")
OUTPUT_VIDEO = os.environ.get("OUTPUT_VIDEO", "response_video")


def main() -> None:
    response = httpx.post(
        f"{BASE_URL}/videos/generations",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "prompt": "A suburban house with a swimming pool at dusk. "
                      "Realistic flamingo is floating in the swimming pool.",
            "aspect_ratio": "16:9 (Widescreen)",
            "megapixels": 0.4,
            "duration": 5,
            "n": 1,
        },
        timeout=1800.0,
    )
    response.raise_for_status()
    data = response.json()
    item = data["data"][0]

    # Prefer b64_json (raw bytes); fall back to downloading the URL.
    if item.get("b64_json"):
        video_bytes = base64.b64decode(item["b64_json"])
    else:
        video_bytes = httpx.get(item["url"]).content

    out_path = f"{OUTPUT_VIDEO}.mp4"
    with open(out_path, "wb") as f:
        f.write(video_bytes)

    print(f"OK - created={data['created']}")
    print(f"url={item['url']}")
    print(f"b64_json len={len(item.get('b64_json') or '')}")
    print(f"saved={out_path}")


if __name__ == "__main__":
    main()
