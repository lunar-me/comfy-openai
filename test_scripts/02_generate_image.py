#!/usr/bin/env python3
"""Minimal test: POST /v1/images/generations — text-to-image.

Run the API server first (python main.py), then:
    python test_scripts/02_generate_image.py
"""

import httpx

from _env import get_api_url, get_env

BASE_URL = get_api_url("http://localhost:8000/v1")
API_KEY = get_env("API_KEY", "local-key")
MODEL = get_env("MODEL", "flux")


def main() -> None:
    response = httpx.post(
        f"{BASE_URL}/images/generations",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "prompt": "A red fox standing in a snowy forest at dusk",
            "size": "1024x1024",
            "n": 1,
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