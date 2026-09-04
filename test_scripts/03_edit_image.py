#!/usr/bin/env python3
"""Minimal test: POST /v1/images/edits — image edit (img2img).

Run the API server first (python main.py), then:
    python test_scripts/03_edit_image.py [input_image] [options]

The prompt can be supplied on the command line, read from a text file, or left
to the default test prompt. The generated image is saved as
``response_image.png`` (override with ``-o``) in the current directory. The
extension is detected from the returned bytes (PNG or JPEG).

Examples:
    python test_scripts/03_edit_image.py
    python test_scripts/03_edit_image.py input.png
    python test_scripts/03_edit_image.py --input-image input.png
    python test_scripts/03_edit_image.py input.png --prompt "Add a tree"
    python test_scripts/03_edit_image.py input.png --prompt-file prompt.txt
    python test_scripts/03_edit_image.py input.png -o edited
"""

import argparse
import base64
import os
from pathlib import Path

import httpx

from _env import api_base_url, load_env

DEFAULT_PROMPT = "Add a realistic flamingo floating in the swimming pool"

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")

load_env()

BASE_URL = api_base_url()
API_KEY = os.environ.get("API_KEY", "local-key")
MODEL = os.environ.get("MODEL", "flux-edit")
DEFAULT_INPUT_IMAGE = os.environ.get("INPUT_IMAGE", "house_and_pool.png")


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments: input image, prompt source, output filename."""
    parser = argparse.ArgumentParser(
        prog="03_edit_image.py",
        description="Edit an existing image from a text prompt (img2img).",
    )
    parser.add_argument(
        "input_image",
        nargs="?",
        default=DEFAULT_INPUT_IMAGE,
        help="Path to the input image. Defaults to the INPUT_IMAGE env var or "
        "'house_and_pool.png'.",
    )
    parser.add_argument(
        "-i",
        "--input-image",
        dest="input_image_override",
        metavar="PATH",
        help="Path to the input image. If present, overrides the positional "
        "input_image argument and the default.",
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
        default=os.environ.get("OUTPUT_IMAGE", "response_image"),
        help="Output image filename. Defaults to the OUTPUT_IMAGE env var or "
        "'response_image'. The format extension (.png/.jpg) is appended after "
        "the response format is detected; a trailing image extension is kept.",
    )
    return parser.parse_args(argv)


def resolve_prompt(args: argparse.Namespace) -> str:
    """Return the prompt from the CLI, from a file, or the default."""
    if args.prompt is not None:
        return args.prompt
    if args.prompt_file is not None:
        return args.prompt_file.read_text(encoding="utf-8").strip()
    return DEFAULT_PROMPT


def resolve_input_image(args: argparse.Namespace) -> str:
    """Return the input image path.

    ``--input-image`` wins over the positional ``input_image`` argument (which
    itself defaults to the ``INPUT_IMAGE`` env var or a fixed default).
    """
    return args.input_image_override or args.input_image


def resolve_output(output: str) -> str:
    """Return the base output path, dropping a trailing image extension if one
    was supplied (the real extension is appended after the format is detected)."""
    lower = output.lower()
    for ext in IMAGE_EXTENSIONS:
        if lower.endswith(ext):
            return output[: -len(ext)]
    return output


def detect_extension(data: bytes) -> str:
    """Detect image format from magic bytes: PNG or JPEG (default PNG)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return ".png"


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    prompt = resolve_prompt(args)
    output_base = resolve_output(args.output)
    input_image = resolve_input_image(args)

    with open(input_image, "rb") as f:
        image_bytes = f.read()

    response = httpx.post(
        f"{BASE_URL}/images/edits",
        headers={"Authorization": f"Bearer {API_KEY}"},
        data={
            "model": MODEL,
            "prompt": prompt,
            "n": 1,
        },
        files={
            "image": (os.path.basename(input_image), image_bytes, "image/png"),
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
    out_path = f"{output_base}{extension}"
    with open(out_path, "wb") as f:
        f.write(image_bytes)

    print(f"OK - created={data['created']}")
    print(f"url={item['url']}")
    print(f"b64_json len={len(item.get('b64_json') or '')}")
    print(f"saved={out_path}")


if __name__ == "__main__":
    main()