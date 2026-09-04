#!/usr/bin/env python3
"""Minimal test: POST /v1/videos/edits — image-to-video.

Run the API server first (python main.py), then:
    python test_scripts/05_generate_video_by_image.py [input_image] [options]

The input image is uploaded together with a text prompt, and the model's
image-to-video workflow animates it. The generated video is saved as
``response_video.mp4`` (override with ``-o``) in the current directory.

Examples:
    python test_scripts/05_generate_video_by_image.py
    python test_scripts/05_generate_video_by_image.py house_and_pool_and_swan.png
    python test_scripts/05_generate_video_by_image.py input.png --prompt "The swan flies away"
    python test_scripts/05_generate_video_by_image.py input.png --prompt-file prompt.txt
    python test_scripts/05_generate_video_by_image.py input.png -o my_video
"""

import argparse
import base64
import os
from pathlib import Path

import httpx

from _env import api_base_url, load_env

DEFAULT_PROMPT = (
    "The swan spreads its wings and lifts off from the swimming pool, "
    "flying away into the dusk sky until it disappears over the treeline."
)

load_env()

BASE_URL = api_base_url()
API_KEY = os.environ.get("API_KEY", "local-key")
MODEL = os.environ.get("MODEL", "minimax-h3-i2v")
DEFAULT_INPUT_IMAGE = os.environ.get("INPUT_IMAGE", "house_and_pool_and_swan.png")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments: input image, prompt source, output filename."""
    parser = argparse.ArgumentParser(
        prog="05_generate_video_by_image.py",
        description="Generate a video from an input image plus a text prompt (image-to-video).",
    )
    parser.add_argument(
        "input_image",
        nargs="?",
        default=DEFAULT_INPUT_IMAGE,
        help="Path to the input image. Defaults to the INPUT_IMAGE env var or "
        "'house_and_pool_and_swan.png'.",
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
        "-m",
        "--megapixels",
        type=float,
        default=float(os.environ.get("MEGAPIXELS", "0.6")),
        help="Target megapixels for the output video. Defaults to the "
        "MEGAPIXELS env var or 0.6.",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=float,
        default=float(os.environ.get("DURATION", "5")),
        help="Video duration in seconds (1-15). Defaults to the DURATION env "
        "var or 5.",
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
    input_image = args.input_image

    with open(input_image, "rb") as f:
        image_bytes = f.read()

    response = httpx.post(
        f"{BASE_URL}/videos/edits",
        headers={"Authorization": f"Bearer {API_KEY}"},
        data={
            "model": MODEL,
            "prompt": prompt,
            "megapixels": str(args.megapixels),
            "duration": str(args.duration),
            "n": 1,
        },
        files={
            "image": (os.path.basename(input_image), image_bytes, "image/png"),
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
