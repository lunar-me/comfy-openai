#!/usr/bin/env python3
"""Minimal test: GET /v1/models — list available image models.

Run the API server first (python main.py), then:
    python test_scripts/01_list_models.py
"""

import os

import httpx

from _env import api_base_url, load_env

load_env()

BASE_URL = api_base_url()
API_KEY = os.environ.get("API_KEY", "local-key")


print(BASE_URL)

def main() -> None:
    response = httpx.get(
        f"{BASE_URL}/models",
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=30.0,
    )
    response.raise_for_status()
    data = response.json()
    models = [m["id"] for m in data["data"]]
    print(f"OK - {len(models)} model(s): {models}")


if __name__ == "__main__":
    main()