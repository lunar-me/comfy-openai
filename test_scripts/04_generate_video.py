#!/usr/bin/env python3
"""Minimal test: POST /v1/videos/generations — text-to-video.

Run the API server: python main.py, then:
    python test_scripts/04_generate_video.py [options]

The prompt can be supplied on the command line, read from a text file, or left
to the default test prompt. The generated video is saved as
``response_video.mp4`` (override with ``-o``) in the current directory.

Examples:
    python test_scripts/04_generate_video.py
    python test_scripts/04_generate_video.py --prompt "A cat surfing at sunset"
    python test_scripts/04_generate_video.py --prompt-file prompt.txt
    python test_scripts/04_generate_video.py -o my_video.mp4
"""

import argparse
import base64
import os
from pathlib import Path

import httpx

from _env import api_base_url, load_env

DEFAULT_PROMPT = (
    "A suburban house with a swimming pool at dusk. "
    "Realistic flamingo is floating in the swimming pool."
)

load_env()

BASE_URL = api_base_url()
API_KEY = os.environ.get("API_KEY", "local-key")
MODEL = os.environ.get("MODEL", "minimax-h3-t2v")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments: prompt source and output filename."""
    parser = argparse.ArgumentParser(
        prog="04_generate_video.py",
        description="Generate a video from a text prompt (text-to-video).",
    )
    parser.add_argument(
        "-p",
        "--prompt",
        help="Prompt text. If omitted and --prompt-file is not given, the "
        "default test prompt is used.",
    )
    parser.add_argument(
        "-f",
        "--prompt-file",
        type=Path,
        help="Path to a text file whose trimmed contents are used as the prompt.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=os.environ.get("OUTPUT_VIDEO", "response_video"),
        help="Output video filename. Defaults to the OUTPUT_VIDEO env var or "
        "'response_video'. A missing '.mp4' extension is appended.",
    )
    return parser.parse_args(argv)


def resolve_prompt(args: argparse.Namespace) -> str:
    """Return the prompt from the CLI, from a file, or the default."""
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file is not None:
        return args.prompt_file.read_text(encoding="utf-8").strip()
    return DEFAULT_PROMPT


def resolve_output(output: str) -> str:
    """Return the output path, ensuring it ends with ``.mp4``."""
    return output if output.lower().endswith(".mp4") else f"{output}.mp4"


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    prompt = resolve_prompt(args)
    out_path = resolve_output(args.output)

    response = httpx.post(
        f"{BASE_URL}/videos/generations",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={
            "model": MODEL,
            "prompt": prompt,
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

    with open(out_path, "wb") as f:
        f.write(video_bytes)

    print(f"OK - created={data['created']}")
    print(f"url={item['url']}")
    print(f"b64_json len={len(item.get('b64_json') or '')}")
    print(f"saved={out_path}")


if __name__ == "__main__":
    main()
