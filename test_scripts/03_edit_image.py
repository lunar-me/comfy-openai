#!/usr/bin/env python3
"""Minimal test: POST /v1/images/edits — image edit (img2img).

Run the API server first (python main.py), then:
    python test_scripts/03_edit_image.py [path_to_input_image]

Example:
    python test_scripts/03_edit_image.py input.png
"""

import os
import sys

import httpx

from _env import get_api_url, get_env

BASE_URL = get_api_url("http://localhost:8000/v1")
API_KEY = get_env("API_KEY", "local-key")
MODEL = get_env("MODEL", "flux-edit")
INPUT_IMAGE = sys.argv[1] if len(sys.argv) > 1 else "input.png"


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
    print(f"OK - created={data['created']}")
    print(f"url={item['url']}")
    print(f"b64_json len={len(item['b64_json'])}")


if __name__ == "__main__":
    main()